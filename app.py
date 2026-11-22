"""BEYONDconnect — single-user BYD dashboard backend (v1.1).

FastAPI + pyBYD, talking to BYD's Indonesia node
(https://dilinkappoversea-id.byd.auto). No accounts, no Google sign-in,
no subscription. Credentials come from environment variables only and
are never written to disk, logs or API responses.

v1.1 adds remote controls (lock / climate / start charging — the 6-digit
BYD control PIN is supplied per request and never stored) and background
trip logging: /api/poll snapshots the car (Vercel Cron daily + a GitHub
Actions workflow every 5 min) into Vercel KV, and /api/trips derives
trips from those snapshots.

Env vars:
  BYD_USERNAME, BYD_PASSWORD   (required — Ray's BYD account)
  BYD_COUNTRY_CODE              (default ID)
  BYD_TIME_ZONE                 (default Asia/Jakarta)
  BYD_BASE_URL                  (default https://dilinkappoversea-id.byd.auto)
  BEYOND_PASSWORD             (optional — if set, /api/status, /api/control
                                 and /api/trips require it as an X-App-Key
                                 header; without it the live location is
                                 visible to anyone with the URL)
  KV_REST_API_URL, KV_REST_API_TOKEN
                              (set automatically when a Vercel KV store is
                               linked to the project; without them background
                               trip logging is off and /api/poll reports
                               kv_not_configured)
  CRON_SECRET                 (optional — if set, /api/poll also accepts
                               Vercel Cron's Bearer token; otherwise it
                               accepts the X-App-Key header)
  TARIFF_RPKWH                (default 1700 — used for trip cost estimates)
  BYD_BATTERY_KWH             (default 60.48 — used for trip energy estimates)
"""
import asyncio
import json
import os
import re
from datetime import datetime, timezone

import aiohttp
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pybyd import BydClient, BydConfig
from pybyd.exceptions import (
    BydControlPasswordError,
    BydEndpointNotSupportedError,
    BydRemoteControlError,
)
from pybyd.models.control import ClimateStartParams, SeatClimateParams

try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")) as _vf:
        VERSION = json.load(_vf)["version"]
except Exception:
    VERSION = "1.2.1"
BASE_URL = os.environ.get("BYD_BASE_URL", "https://dilinkappoversea-id.byd.auto")
COUNTRY = os.environ.get("BYD_COUNTRY_CODE", "ID")
TIME_ZONE = os.environ.get("BYD_TIME_ZONE", "Asia/Jakarta")
APP_PASSWORD = os.environ.get("BEYOND_PASSWORD", "")

app = FastAPI(title="BEYONDconnect", version=VERSION)

_lock = asyncio.Lock()
_client: BydClient | None = None
_session: aiohttp.ClientSession | None = None


def _configured() -> bool:
    return bool(os.environ.get("BYD_USERNAME") and os.environ.get("BYD_PASSWORD"))


def _mask_vin(vin: str) -> str:
    return (vin[:3] + "…" + vin[-4:]) if vin and len(vin) > 7 else "***"


async def _new_client() -> BydClient:
    global _session
    config = BydConfig(
        username=os.environ["BYD_USERNAME"],
        password=os.environ["BYD_PASSWORD"],
        base_url=BASE_URL,
        country_code=COUNTRY,
        time_zone=TIME_ZONE,
        mqtt_enabled=False,
    )
    _session = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True), trust_env=True
    )
    client = BydClient(config, session=_session)
    await client.async_start()
    await client.login()
    return client


async def _get_client() -> BydClient:
    global _client
    async with _lock:
        if _client is None:
            _client = await _new_client()
        return _client


async def _reset_client() -> None:
    global _client, _session
    async with _lock:
        if _client is not None:
            try:
                await _client.async_close()
            except Exception:
                pass
        if _session is not None:
            try:
                await _session.close()
            except Exception:
                pass
        _client = None
        _session = None


def _num(v):
    return None if v is None else float(v)


@app.get("/api/health")
async def health():
    return {"ok": True, "version": VERSION, "configured": _configured(),
            "needs_key": bool(APP_PASSWORD)}


@app.get("/api/status")
async def status(x_app_key: str | None = Header(default=None)):
    if APP_PASSWORD and x_app_key != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="app key required")
    if not _configured():
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "not_configured",
                     "hint": "Set BYD_USERNAME and BYD_PASSWORD env vars."},
        )
    for attempt in range(2):
        try:
            client = await _get_client()
            vehicles = await client.get_vehicles()
            if not vehicles:
                return JSONResponse(status_code=502, content={
                    "ok": False, "error": "no_vehicles"})
            v = vehicles[0]
            vin = v.vin
            # Independent calls in parallel — BYD answers each in ~1s,
            # sequential would be ~6s per refresh.
            async def _safe(coro):
                try:
                    return await coro
                except Exception:
                    return None
            rt, gps, ch, en, hv = await asyncio.gather(
                client.get_vehicle_realtime(vin),
                # GPS flakes transiently (BYD code 1008) — never let it
                # take the whole dashboard down.
                _safe(client.get_gps_info(vin)),
                _safe(client.get_charging_status(vin)),
                _safe(client.get_energy_consumption(vin)),
                _safe(client.get_hvac_status(vin)),
            )
            if ch is not None:
                charging = {"soc": ch.soc, "charging_state": ch.charging_state,
                            "connect_state": ch.connect_state,
                            "charge_power": _num(ch.charge_power),
                            "update_time": ch.update_time.isoformat()
                            if ch.update_time else None}
            else:
                charging = None
            if en is not None:
                energy = {
                    "avg_ev": _num(en.cumulative_energy_consumption.avg_ev_consumption),
                    "recent_ev": _num(en.nearest_energy_consumption.avg_ev_consumption),
                    "self_graph": en.self_graph.energy_consumption or [],
                    "self_unit": en.self_graph.energy_consumption_unit or "kWh/100km",
                }
            else:
                energy = None
            if hv is not None:
                # BYD sends 0.0 / -1 sentinels when the car is asleep or
                # charging-only — a 0 °C outside temp or 0 °C set temp is
                # not real (valid set range is 17–33 °C).
                def _temp(v):
                    n = _num(v)
                    return None if n is None or n == 0.0 else n
                def _st(v):
                    return None if v is None or int(v) == -1 else int(v)
                def _seat(v):
                    # SeatHeatVentState: 0=no data, 1=off, 2=low, 3=high.
                    return None if v is None else int(v)
                hvac = {"temp_in_car": _temp(hv.temp_in_car),
                        "temp_out_car": _temp(hv.temp_out_car),
                        "ac_switch": _st(hv.ac_switch), "status": _st(hv.status),
                        "main_setting_temp": _temp(hv.main_setting_temp),
                        "set_temp_c": _temp(hv.main_setting_temp_new),
                        "cycle": _st(hv.cycle_choice),
                        "fan": _st(hv.wind_position),
                        "seats": {
                            "driver": {"heat": _seat(hv.main_seat_heat_state),
                                       "vent": _seat(hv.main_seat_ventilation_state)},
                            "copilot": {"heat": _seat(hv.copilot_seat_heat_state),
                                        "vent": _seat(hv.copilot_seat_ventilation_state)},
                            "rear_left": {"heat": _seat(hv.lr_seat_heat_state),
                                          "vent": _seat(hv.lr_seat_ventilation_state)},
                            "rear_right": {"heat": _seat(hv.rr_seat_heat_state),
                                           "vent": _seat(hv.rr_seat_ventilation_state)}}}
            else:
                hvac = None
            return {
                "ok": True,
                "version": VERSION,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "vehicle": {
                    "vin": vin,
                    "vin_masked": _mask_vin(vin),
                    "model_name": v.model_name,
                    "alias": v.auto_alias,
                    "plate": v.auto_plate,
                    "pic_url": v.pic_main_url,
                    "odometer_km": _num(v.total_mileage),
                    "bought": v.auto_bought_time.isoformat()
                    if v.auto_bought_time else None,
                },
                "realtime": {
                    "battery_pct": _num(rt.elec_percent),
                    "range_km": _num(rt.endurance_mileage),
                    "odometer_km": _num(rt.total_mileage),
                    "speed_kmh": _num(rt.speed),
                    "online_state": int(rt.online_state),
                    "charging_state": int(rt.charging_state),
                    "temp_in_car": _num(rt.temp_in_car),
                    "charge_power_kw": _num(rt.charge_power),
                    "full_hour": rt.full_hour,
                    "full_minute": rt.full_minute,
                    "remaining_hours": rt.remaining_hours,
                    "remaining_minutes": rt.remaining_minutes,
                    "energy_lifetime_kwh100": _num(rt.total_energy_ev),
                    "energy_recent_kwh100": _num(rt.recent_50km_energy_ev),
                    "doors": {"fl": int(rt.left_front_door) if rt.left_front_door is not None else None,
                              "fr": int(rt.right_front_door) if rt.right_front_door is not None else None,
                              "rl": int(rt.left_rear_door) if rt.left_rear_door is not None else None,
                              "rr": int(rt.right_rear_door) if rt.right_rear_door is not None else None,
                              "trunk": int(rt.trunk_lid) if rt.trunk_lid is not None else None,
                              "hood": int(rt.forehold) if rt.forehold is not None else None},
                    "locks": {"fl": int(rt.left_front_door_lock) if rt.left_front_door_lock is not None else None,
                              "fr": int(rt.right_front_door_lock) if rt.right_front_door_lock is not None else None,
                              "rl": int(rt.left_rear_door_lock) if rt.left_rear_door_lock is not None else None,
                              "rr": int(rt.right_rear_door_lock) if rt.right_rear_door_lock is not None else None},
                    "windows": {"fl": int(rt.left_front_window) if rt.left_front_window is not None else None,
                                "fr": int(rt.right_front_window) if rt.right_front_window is not None else None,
                                "rl": int(rt.left_rear_window) if rt.left_rear_window is not None else None,
                                "rr": int(rt.right_rear_window) if rt.right_rear_window is not None else None},
                    "tyres_psi": {"fl": _num(rt.left_front_tire_pressure),
                                  "fr": _num(rt.right_front_tire_pressure),
                                  "rl": _num(rt.left_rear_tire_pressure),
                                  "rr": _num(rt.right_rear_tire_pressure)},
                    "timestamp": rt.timestamp.isoformat() if rt.timestamp else None,
                },
                "gps": ({"lat": _num(gps.latitude), "lon": _num(gps.longitude),
                         "speed_kmh": _num(gps.speed),
                         "direction": _num(gps.direction),
                         "timestamp": gps.gps_timestamp.isoformat()
                         if gps.gps_timestamp else None} if gps else None),
                "charging": charging,
                "energy": energy,
                "hvac": hvac,
            }
        except Exception as e:
            await _reset_client()
            if attempt == 1:
                msg = str(e)
                code = "byd_auth_failed" if "3008" in msg or "Authentication" in type(e).__name__ else "byd_error"
                return JSONResponse(status_code=502, content={
                    "ok": False, "error": code, "detail": msg[:200]})
    return JSONResponse(status_code=502, content={"ok": False, "error": "byd_error"})


# ---------------------------------------------------------------------------
# Remote controls (v1.1)
# ---------------------------------------------------------------------------
# pyBYD facts (read from the installed 0.0.88 source, not guessed):
# - lock/unlock/start_climate/stop_climate need the 6-digit control PIN and
#   require verify_command_access(vin, command_pwd=pin) once per client
#   instance before the first command. The PIN is MD5-hashed by pyBYD.
# - start_charging needs no PIN (gated on capability 1012).
# - stop_charging does NOT exist: pyBYD raises BydEndpointNotSupportedError
#   because BYD's cloud stop-charge call is a verified no-op (returns
#   success but the car keeps charging). The only way to stop a charge is
#   the key-fob / door-handle double-unlock. We do not offer a stop button.

def _require_app_key(x_app_key: str | None) -> None:
    if APP_PASSWORD and x_app_key != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="app key required")


_PIN_RE = re.compile(r"^\d{6}$")


@app.post("/api/control")
async def control(
    request: Request,
    x_app_key: str | None = Header(default=None),
):
    _require_app_key(x_app_key)
    if not _configured():
        return JSONResponse(status_code=503, content={
            "ok": False, "error": "not_configured"})
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = str(body.get("action") or "")
    pin = str(body.get("pin") or "")
    if action in ("lock", "unlock", "climate_start", "climate_stop",
                  "seat_climate", "find_car", "flash_lights",
                  "open_windows", "close_windows", "open_trunk",
                  "close_trunk"):
        if not _PIN_RE.match(pin):
            return JSONResponse(status_code=400, content={
                "ok": False, "error": "bad_pin",
                "detail": "A 6-digit BYD control PIN is required."})
    elif action in ("charge_start", "charge_stop"):
        pass
    else:
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "bad_action",
            "detail": "action must be lock, unlock, climate_start, "
                      "climate_stop, seat_climate, find_car, flash_lights, "
                      "open_windows, close_windows, open_trunk, close_trunk "
                      "or charge_start."})
    if action == "charge_stop":
        # Honest no-op: the cloud cannot stop a charge (see header note).
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "stop_unsupported",
            "detail": "BYD's cloud has no working stop-charge command — it "
                      "returns success but the car keeps charging. Stop a "
                      "charge with the key fob / door-handle double-unlock."})
    try:
        client = await _get_client()
        vehicles = await client.get_vehicles()
        if not vehicles:
            return JSONResponse(status_code=502, content={
                "ok": False, "error": "no_vehicles"})
        vin = vehicles[0].vin
        if action != "charge_start" and not client.commands_enabled:
            try:
                await client.verify_command_access(vin, command_pwd=pin)
            except BydControlPasswordError:
                return JSONResponse(status_code=403, content={
                    "ok": False, "error": "bad_pin",
                    "detail": "Wrong control PIN, or the account is locked "
                              "after too many wrong attempts."})
        if action == "lock":
            res = await client.lock(vin, command_pwd=pin)
        elif action == "unlock":
            res = await client.unlock(vin, command_pwd=pin)
        elif action == "climate_start":
            temp = body.get("temperature")
            try:
                temp = float(temp) if temp is not None else 23.0
            except (TypeError, ValueError):
                temp = 23.0
            temp = min(31.0, max(15.0, temp))
            dur = body.get("duration_min")
            try:
                dur = int(dur) if dur is not None else 30
            except (TypeError, ValueError):
                dur = 30
            span = min(5, max(1, (dur + 4) // 5))  # 10..30 min -> code 1..5
            cycle = body.get("cycle_mode")
            try:
                cycle = int(cycle) if cycle is not None else 2
            except (TypeError, ValueError):
                cycle = 2
            cycle = 1 if cycle == 1 else 2  # 1=fresh air, 2=recirculate
            fan = body.get("fan_level")
            try:
                fan = int(fan) if fan is not None else None
            except (TypeError, ValueError):
                fan = None
            fan = fan if fan is not None and 1 <= fan <= 7 else None
            if body.get("adjust"):
                # Setpoint tweak of a running session: keep the session
                # and its auto-off timer (air_set "14").
                hv_now = None
                try:
                    hv_now = await client.get_hvac_status(vin)
                except Exception:
                    hv_now = None
                if hv_now is not None and hv_now.is_ac_on:
                    res = await client.start_climate(
                        vin, params=ClimateStartParams(temperature=temp,
                                                        air_set="14"),
                        command_pwd=pin)
                else:
                    res = await client.start_climate(
                        vin, params=ClimateStartParams(
                            temperature=temp, time_span=span,
                            cycle_mode=cycle, wind_level=fan),
                        command_pwd=pin)
            else:
                res = await client.start_climate(
                    vin, params=ClimateStartParams(
                        temperature=temp, time_span=span,
                        cycle_mode=cycle, wind_level=fan),
                    command_pwd=pin)
        elif action == "seat_climate":
            # Seat ventilation (and heat) — the API requires ALL seat
            # values in every command, so build from the current state
            # and change only the requested seat (pyBYD factory).
            seat = str(body.get("seat") or "")
            mode = str(body.get("mode") or "")
            level = body.get("level")
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = -1
            _SEAT_PARAM = {
                ("driver", "heat"): "main_heat",
                ("driver", "vent"): "main_ventilation",
                ("copilot", "heat"): "copilot_heat",
                ("copilot", "vent"): "copilot_ventilation",
                ("rear_left", "heat"): "lr_seat_heat_state",
                ("rear_left", "vent"): "lr_seat_ventilation_state",
                ("rear_right", "heat"): "rr_seat_heat_state",
                ("rear_right", "vent"): "rr_seat_ventilation_state",
            }
            key = _SEAT_PARAM.get((seat, mode))
            if key is None or level not in (0, 1, 2):
                return JSONResponse(status_code=400, content={
                    "ok": False, "error": "bad_seat",
                    "detail": "seat must be driver/copilot/rear_left/"
                              "rear_right, mode heat/vent, level 0/1/2."})
            # UI level 0=off, 1=low, 2=high -> command scale 3/2/1.
            cmd_level = {0: 3, 1: 2, 2: 1}[level]
            hv_now = rt_now = None
            try:
                hv_now = await client.get_hvac_status(vin)
            except Exception:
                hv_now = None
            try:
                rt_now = await client.get_vehicle_realtime(vin)
            except Exception:
                rt_now = None
            params = SeatClimateParams.from_current_state(hv_now, rt_now)
            params = params.with_change(key, cmd_level)
            res = await client.set_seat_climate(
                vin, params=params, command_pwd=pin)
        elif action == "climate_stop":
            res = await client.stop_climate(vin, command_pwd=pin)
        elif action == "find_car":
            # Horn + lights.
            res = await client.find_car(vin, command_pwd=pin)
        elif action == "flash_lights":
            res = await client.flash_lights(vin, command_pwd=pin)
        elif action == "open_windows":
            # BYD vents the windows to a ~10% crack, not a full drop.
            res = await client.open_windows(vin, command_pwd=pin)
        elif action == "close_windows":
            res = await client.close_windows(vin, command_pwd=pin)
        elif action == "open_trunk":
            # Gated by functionNo 1020 (OPENTRUNK) in Latest Config —
            # may be unsupported on this car (400 not_supported).
            res = await client.open_trunk(vin, command_pwd=pin)
        elif action == "close_trunk":
            # Gated by functionNo 1021 (CLOSETRUNK) in Latest Config.
            res = await client.close_trunk(vin, command_pwd=pin)
        elif action == "charge_start":
            res = await client.start_charging(vin)
            return {"ok": True, "action": action,
                    "result": {"res": res.res, "message": res.message}}
        return {"ok": True, "action": action,
                "result": {"success": bool(res.success),
                           "state": str(res.control_state)}}
    except BydEndpointNotSupportedError as e:
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "not_supported", "detail": str(e)[:200]})
    except BydRemoteControlError as e:
        msg = str(e)
        code = "already_charging" if "already" in msg.lower() else "command_failed"
        return JSONResponse(status_code=502, content={
            "ok": False, "error": code, "detail": msg[:200]})
    except Exception as e:
        msg = str(e)
        code = "byd_auth_failed" if "3008" in msg else "byd_error"
        return JSONResponse(status_code=502, content={
            "ok": False, "error": code, "detail": msg[:200]})


# ---------------------------------------------------------------------------
# Background trip logging (v1.1) — Vercel KV via the Upstash REST API.
# ---------------------------------------------------------------------------
# No new account needed: a KV store is created in the Vercel dashboard
# (Storage -> Create Database -> KV) and linked to the project, which sets
# KV_REST_API_URL / KV_REST_API_TOKEN automatically. Without them, /api/poll
# reports kv_not_configured and /api/trips returns an empty list — the
# browser-local trip history keeps working on its own.
KV_URL = os.environ.get("KV_REST_API_URL", "").rstrip("/")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN", "")
KV_SNAPS_KEY = "beyond:snaps"
KV_MAX_SNAPS = 3000  # ~10 days at a 5-minute cadence
CRON_SECRET = os.environ.get("CRON_SECRET", "")
TARIFF_RPKWH = float(os.environ.get("TARIFF_RPKWH", "1700") or 1700)
BATTERY_KWH = float(os.environ.get("BYD_BATTERY_KWH", "60.48") or 60.48)


async def _kv(args: list[str], method: str = "POST") -> dict | None:
    """One Upstash REST call. Returns the parsed JSON, or None on failure."""
    if not KV_URL or not KV_TOKEN:
        return None
    url = KV_URL + "/" + "/".join(args)
    try:
        async with aiohttp.ClientSession(trust_env=True) as s:
            async with s.request(
                method, url,
                headers={"Authorization": f"Bearer {KV_TOKEN}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    return None
                return await r.json()
    except Exception:
        return None


def _home_location(snaps: list[dict]) -> tuple | None:
    """The car's home: the most common ~1 km grid cell across snapshots,
    then the median point inside that cell. The car is parked at home most
    of the time, so the mode is home. (The old median of ALL snapshots
    lands in the middle of a long drive's route when the snapshots split
    between two places — after the Cikarang→BSD drive it returned a point
    ~26 km from either end, so nothing was ever detected as "Home".)"""
    from collections import Counter
    pts = [(s["lat"], s["lon"]) for s in snaps
           if isinstance(s.get("lat"), (int, float))
           and isinstance(s.get("lon"), (int, float))]
    if len(pts) < 10:
        return None
    cells = Counter((round(la, 2), round(lo, 2)) for la, lo in pts)
    cell, _ = cells.most_common(1)[0]
    in_cell = sorted((la, lo) for la, lo in pts
                     if (round(la, 2), round(lo, 2)) == cell)
    return in_cell[len(in_cell) // 2]


def _haversine_km(a: tuple, b: tuple) -> float:
    import math
    lat1, lon1, lat2, lon2 = (math.radians(x) for x in (*a, *b))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) *
         math.sin(dlon / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def _derive_trips(snaps: list[dict], tariff: float, batt_kwh: float) -> list[dict]:
    """Group snapshots into trips: a trip is a run of snapshots where the
    odometer keeps increasing (gaps under 30 min). Needs >= 0.5 km."""
    home = _home_location(snaps)

    def place(s):
        if home is None:
            return None
        lat, lon = s.get("lat"), s.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return None
        return "Home" if _haversine_km(home, (lat, lon)) < 0.5 else None
    trips = []
    cur = None  # [first_snap, last_moving_snap]
    prev = None
    for s in snaps:
        odo = s.get("odo_km")
        if odo is None:
            prev = s
            continue
        if prev is not None and prev.get("odo_km") is not None:
            moved = odo - prev["odo_km"]
            gap_min = None
            try:
                gap_min = (datetime.fromisoformat(s["t"]) -
                           datetime.fromisoformat(prev["t"])).total_seconds() / 60
            except Exception:
                pass
            if moved > 0 and (gap_min is None or gap_min < 30):
                if cur is None:
                    cur = [prev, s]
                else:
                    cur[1] = s
            else:
                if cur is not None:
                    trips.append(cur)
                    cur = None
        prev = s
    if cur is not None:
        trips.append(cur)
    # Merge segments split by a brief stop: a single drive is often cut in
    # two when the car sits still for one poll (traffic light, quick stop)
    # and the odometer doesn't move for that interval, so the loop above
    # closes the trip and a new one starts when it moves again. Join
    # segments whose stationary gap is under 10 min so they read as one
    # trip; a real stop (parked 10+ min at a destination) stays separate.
    MERGE_GAP_MIN = 10
    merged = []
    for seg in trips:
        if merged:
            prev_first, prev_last = merged[-1]
            try:
                gap = (datetime.fromisoformat(seg[0]["t"]) -
                       datetime.fromisoformat(prev_last["t"])).total_seconds() / 60
            except Exception:
                gap = None
            if gap is not None and gap < MERGE_GAP_MIN:
                merged[-1][1] = seg[1]
                continue
        merged.append([seg[0], seg[1]])
    trips = merged
    out = []
    for first, last in trips:
        dist = round(last["odo_km"] - first["odo_km"], 1)
        if dist < 0.5:
            continue
        batt_drop = (first.get("batt_pct") or 0) - (last.get("batt_pct") or 0)
        energy = round(batt_drop / 100 * batt_kwh, 2) if batt_drop > 0 else None
        try:
            dur_min = round((datetime.fromisoformat(last["t"]) -
                             datetime.fromisoformat(first["t"])).total_seconds() / 60)
        except Exception:
            dur_min = None
        out.append({
            "start_time": first["t"], "end_time": last["t"],
            "start_odo_km": first["odo_km"], "end_odo_km": last["odo_km"],
            "distance_km": dist,
            "duration_min": dur_min,
            "avg_speed_kmh": round(dist / (dur_min / 60), 1)
            if dur_min and dur_min > 0 else None,
            "start_batt_pct": first.get("batt_pct"),
            "end_batt_pct": last.get("batt_pct"),
            "batt_used_pct": round(batt_drop, 1) if batt_drop > 0 else None,
            "energy_kwh": energy,
            "eff_kwh100": round(energy / dist * 100, 1)
            if energy is not None and dist > 0 else None,
            "est_cost_rp": round(energy * tariff) if energy is not None else None,
            "start_lat": first.get("lat"), "start_lon": first.get("lon"),
            "end_lat": last.get("lat"), "end_lon": last.get("lon"),
            "start_place": place(first), "end_place": place(last),
            "points": [{"t": s.get("t"), "lat": s.get("lat"),
                        "lon": s.get("lon"), "batt_pct": s.get("batt_pct")}
                       for s in snaps
                       if first["t"] <= s.get("t", "") <= last["t"]
                       and isinstance(s.get("lat"), (int, float))
                       and isinstance(s.get("lon"), (int, float))],
        })
    return list(reversed(out))  # newest first


def _charging_sessions(snaps: list[dict]) -> list[dict]:
    """Charging sessions: runs of charging snapshots (gaps < 30 min).
    Energy is charge power integrated over time (trapezoid rule on the
    5-minute snapshots). A session counts when it has >= 2 points, the
    battery actually gained (>= 1%) and energy > 0 — short top-ups count
    too. Newest first. The capacity estimate (below) applies stricter
    filters to the same list, so its math is unchanged."""
    def _dt(a, b):
        try:
            return (datetime.fromisoformat(b["t"]) -
                    datetime.fromisoformat(a["t"])).total_seconds() / 3600
        except Exception:
            return None

    sessions: list[dict] = []
    run: list[dict] = []

    def flush(run):
        if len(run) < 2:
            return
        first, last = run[0], run[-1]
        # Regen braking is not charging: if the car drove during this run
        # (odometer moved), it was regen while driving, not a plug-in
        # session. Real charging happens with the car parked. This also
        # drops false sessions from snapshots written before the poll
        # fix above started requiring the gun to be connected.
        odo_first = first.get("odo_km")
        odo_last = last.get("odo_km")
        if (odo_first is not None and odo_last is not None
                and odo_last - odo_first > 0.5):
            return
        dsoc = (last.get("batt_pct") or 0) - (first.get("batt_pct") or 0)
        if dsoc < 1:
            return
        energy = 0.0
        for a, b in zip(run, run[1:]):
            pa, pb = a.get("power_kw"), b.get("power_kw")
            dt_h = _dt(a, b)
            if pa is None or pb is None or dt_h is None:
                continue
            if dt_h <= 0 or dt_h > 0.5:
                continue
            energy += (pa + pb) / 2 * dt_h
        if energy <= 0:
            return
        try:
            dur = round((datetime.fromisoformat(last["t"]) -
                         datetime.fromisoformat(first["t"])).total_seconds() / 60)
        except Exception:
            dur = None
        cap = energy / (dsoc / 100)
        sessions.append({
            "start_time": first.get("t"), "end_time": last.get("t"),
            "duration_min": dur,
            "start_batt_pct": first.get("batt_pct"),
            "end_batt_pct": last.get("batt_pct"),
            "energy_kwh": round(energy, 2),
            "n_points": len(run),
            "dsoc": dsoc,
            "capacity_kwh": cap if 30 <= cap <= 60 else None,
            "start_odo_km": first.get("odo_km"),
            "lat": first.get("lat"), "lon": first.get("lon"),
            "points": [{"t": s.get("t"), "power_kw": s.get("power_kw"),
                        "batt_pct": s.get("batt_pct")} for s in run],
        })

    prev = None
    for s in snaps:
        if s.get("charging"):
            if prev is not None and prev.get("charging"):
                try:
                    gap = (datetime.fromisoformat(s["t"]) -
                           datetime.fromisoformat(prev["t"])).total_seconds() / 60
                except Exception:
                    gap = None
                if gap is not None and gap >= 30:
                    flush(run)
                    run = []
            run.append(s)
        else:
            flush(run)
            run = []
        prev = s
    flush(run)
    return list(reversed(sessions))  # newest first


def _capacity_estimates(snaps: list[dict], trips: list[dict]) -> list:
    """Implied full usable capacity (kWh) from history, as a list of
    (capacity_kwh, weight, kind) — shared by the SOH and range estimates.

    Derived two ways, both implying the full usable capacity:
    - Charging sessions: integrate charge power over time (trapezoid rule
      on the 5-minute snapshots) and divide by the SOC gained.
    - Trips: distance x the car's own measured efficiency (kWh/100 km,
      stored per snapshot) divided by the SOC dropped.
    Only sessions with >= 10 points of SOC change (>= 5 for trips) and an
    implied capacity in a sane 30-60 kWh band count.
    """
    estimates = []  # (capacity_kwh, weight, kind)
    # --- charging sessions: the strict subset of _charging_sessions ---
    for s in _charging_sessions(snaps):
        if (s["n_points"] >= 4 and s["dsoc"] >= 10
                and s["capacity_kwh"] is not None):
            estimates.append((s["capacity_kwh"], s["dsoc"], "charge"))
    # --- trips: distance x measured efficiency / SOC dropped ---
    for t in trips:
        drop = (t.get("start_batt_pct") or 0) - (t.get("end_batt_pct") or 0)
        if drop < 5 or (t.get("distance_km") or 0) < 5:
            continue
        effs = [s.get("eff_kwh100") for s in snaps
                if t["start_time"] <= s.get("t", "") <= t["end_time"]
                and s.get("eff_kwh100")]
        if not effs:
            continue
        eff = sum(effs) / len(effs)
        cap = t["distance_km"] * eff / 100 / (drop / 100)
        if 30 <= cap <= 60:
            estimates.append((cap, drop, "trip"))
    return estimates


def _estimate_soh(snaps: list[dict], trips: list[dict],
                  batt_kwh: float) -> dict | None:
    """Battery state-of-health from history: the implied capacity (see
    _capacity_estimates) averaged weighted by |dSOC|, vs the nominal pack.
    Returns None when there is no usable history yet."""
    estimates = _capacity_estimates(snaps, trips)
    if not estimates:
        return None
    wsum = sum(w for _, w, _ in estimates)
    cap_avg = sum(c * w for c, w, _ in estimates) / wsum
    return {
        "soh_pct": round(100 * cap_avg / batt_kwh, 1),
        "capacity_kwh": round(cap_avg, 1),
        "nominal_kwh": batt_kwh,
        "charge_sessions": sum(1 for _, _, k in estimates if k == "charge"),
        "trip_estimates": sum(1 for _, _, k in estimates if k == "trip"),
    }


def _estimate_range(snaps: list[dict], trips: list[dict],
                    batt_kwh: float) -> dict | None:
    """Range from the car's own history, not BYD's dashboard number:
    implied usable capacity (from charging sessions + trips, else the
    nominal pack) divided by the efficiency the car actually drove at.

    Efficiency comes from the car's own meter first (recent 50 km in the
    latest snapshot), falling back to the trips only when the car gives
    no reading. Returns None until at least one efficiency reading
    exists. range_now_km is the range at the latest battery %."""
    estimates = _capacity_estimates(snaps, trips)
    if estimates:
        wsum = sum(w for _, w, _ in estimates)
        cap = sum(c * w for c, w, _ in estimates) / wsum
        cap_source = "history"
    else:
        cap = batt_kwh
        cap_source = "nominal"
    # Efficiency: prefer the car's own measured figure (recent 50 km,
    # from the latest snapshot) — it comes from the car's energy meter
    # and is precise. Trip-derived efficiency (battery-% drop x nominal
    # pack / distance) is coarse: the battery % is an integer, so on a
    # short trip a 1% rounding error swings the efficiency by a third
    # and the range with it (a single 18 km trip read 10.1 kWh/100km
    # and gave 599 km full, vs the car's own 14.1 -> 429 km). Only fall
    # back to the trips when the car gives no efficiency reading.
    eff = None
    for s in reversed(snaps):
        if s.get("eff_kwh100"):
            eff = s["eff_kwh100"]
            break
    if eff is not None:
        eff_source = "car"
    else:
        eff_num = eff_den = 0.0
        for t in trips:
            e = t.get("eff_kwh100")
            d = t.get("distance_km") or 0
            if e and d > 0:
                eff_num += e * d
                eff_den += d
        if eff_den > 0:
            eff = eff_num / eff_den
            eff_source = "trips"
        else:
            return None
    batt_now = None
    for s in reversed(snaps):
        if s.get("batt_pct") is not None:
            batt_now = s["batt_pct"]
            break
    if batt_now is None:
        return None
    full = cap / eff * 100
    return {
        "range_full_km": round(full),
        "range_now_km": round(full * batt_now / 100),
        "eff_kwh100": round(eff, 1),
        "eff_source": eff_source,
        "capacity_kwh": round(cap, 1),
        "capacity_source": cap_source,
        "batt_pct": batt_now,
        "trips_used": sum(1 for t in trips if t.get("eff_kwh100")),
        "charge_sessions": sum(1 for _, _, k in estimates if k == "charge"),
    }


@app.get("/api/poll")
async def poll(
    request: Request,
    x_app_key: str | None = Header(default=None),
):
    """Snapshot the car for background trip logging. Called by Vercel Cron
    (Bearer CRON_SECRET) or the GitHub Actions workflow (X-App-Key)."""
    cron_secret = os.environ.get("CRON_SECRET", "")
    auth = request.headers.get("authorization", "")
    cron_ok = bool(cron_secret) and auth == f"Bearer {cron_secret}"
    if not cron_ok:
        _require_app_key(x_app_key)
    if not _configured():
        return JSONResponse(status_code=503, content={
            "ok": False, "error": "not_configured"})
    if not KV_URL or not KV_TOKEN:
        return JSONResponse(status_code=503, content={
            "ok": False, "error": "kv_not_configured",
            "hint": "Create a Vercel KV store and link it to this project."})
    try:
        client = await _get_client()
        vehicles = await client.get_vehicles()
        if not vehicles:
            return JSONResponse(status_code=502, content={
                "ok": False, "error": "no_vehicles"})
        vin = vehicles[0].vin

        async def _safe(coro):
            try:
                return await coro
            except Exception:
                return None

        rt, gps, ch = await asyncio.gather(
            client.get_vehicle_realtime(vin),
            _safe(client.get_gps_info(vin)),
            _safe(client.get_charging_status(vin)),
        )
        snap = {
            "t": datetime.now(timezone.utc).isoformat(),
            "odo_km": _num(rt.total_mileage),
            "batt_pct": _num(rt.elec_percent),
            "lat": _num(gps.latitude) if gps else None,
            "lon": _num(gps.longitude) if gps else None,
            # Regen braking is not charging: the gun must be plugged in.
            # charging_state alone reads 1 while regenerating (energy
            # flowing into the battery), but connect_state is 0 then —
            # pyBYD's is_connected (connect_state > 0) is the plug state.
            "charging": bool(ch and ch.charging_state == 1 and ch.is_connected),
            "power_kw": _num(ch.charge_power) if ch else None,
            # The car's own measured efficiency — feeds the trip-side
            # SOH estimate (distance x efficiency / SOC dropped).
            "eff_kwh100": _num(rt.recent_50km_energy_ev),
        }
        import urllib.parse
        await _kv(["lpush", KV_SNAPS_KEY,
                   urllib.parse.quote(json.dumps(snap), safe="")])
        await _kv(["ltrim", KV_SNAPS_KEY, "0", str(KV_MAX_SNAPS - 1)])
        return {"ok": True, "snapshot": snap}
    except Exception as e:
        await _reset_client()
        return JSONResponse(status_code=502, content={
            "ok": False, "error": "byd_error", "detail": str(e)[:200]})


@app.get("/api/trips")
async def trips(
    request: Request,
    x_app_key: str | None = Header(default=None),
    tariff: float | None = None,
):
    _require_app_key(x_app_key)
    if not KV_URL or not KV_TOKEN:
        return {"ok": True, "source": "none", "trips": [], "snapshots": 0,
                "charging_sessions": [],
                "note": "Background logging is off — no Vercel KV store "
                        "linked. Browser-local trips still work."}
    res = await _kv(["lrange", KV_SNAPS_KEY, "0", str(KV_MAX_SNAPS - 1)],
                    method="GET")
    snaps = []
    if res and isinstance(res.get("result"), list):
        for raw in res["result"]:
            try:
                snaps.append(json.loads(raw))
            except Exception:
                pass
    snaps.sort(key=lambda s: s.get("t", ""))
    trips = _derive_trips(snaps, tariff or TARIFF_RPKWH, BATTERY_KWH)
    t = tariff or TARIFF_RPKWH
    home = _home_location(snaps)
    sessions = []
    for s in _charging_sessions(snaps):
        place = None
        lat, lon = s.get("lat"), s.get("lon")
        if home is not None and isinstance(lat, (int, float)) \
                and isinstance(lon, (int, float)):
            place = "Home" if _haversine_km(home, (lat, lon)) < 0.5 else None
        sessions.append({
            "start_time": s["start_time"], "end_time": s["end_time"],
            "duration_min": s["duration_min"],
            "start_batt_pct": s["start_batt_pct"],
            "end_batt_pct": s["end_batt_pct"],
            "energy_kwh": s["energy_kwh"],
            "est_cost_rp": round(s["energy_kwh"] * t),
            "start_odo_km": s.get("start_odo_km"),
            "place": place,
            "points": s["points"],
        })
    return {"ok": True, "source": "server", "trips": trips,
            "snapshots": len(snaps), "charging_sessions": sessions,
            "home": list(home) if home else None,
            "soh": _estimate_soh(snaps, trips, BATTERY_KWH),
            "range": _estimate_range(snaps, trips, BATTERY_KWH)}


# Serve the static frontend (public/). Path is anchored to this file, not the
# process working directory — on Vercel the function runs from /var/task and
# the relative "public" path does not exist there (import failed with
# RuntimeError: Directory 'public' does not exist). vercel.json also lists
# public/** in includeFiles so the directory is bundled into the function.
from pathlib import Path as _Path
BASE_DIR = _Path(__file__).resolve().parent


@app.get("/version.json")
def version_file():
    return FileResponse(BASE_DIR / "version.json", media_type="application/json")


app.mount("/", StaticFiles(directory=BASE_DIR / "public", html=True), name="public")
