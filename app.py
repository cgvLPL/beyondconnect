"""BEYONDconnect — single-user BYD dashboard backend (v1, read-only).

FastAPI + pyBYD, talking to BYD's Indonesia node
(https://dilinkappoversea-id.byd.auto). No accounts, no Google sign-in,
no subscription. Credentials come from environment variables only and
are never written to disk, logs or API responses.

Env vars:
  BYD_USERNAME, BYD_PASSWORD   (required — Ray's BYD account)
  BYD_COUNTRY_CODE              (default ID)
  BYD_TIME_ZONE                 (default Asia/Jakarta)
  BYD_BASE_URL                  (default https://dilinkappoversea-id.byd.auto)
  BEYOND_PASSWORD             (optional — if set, /api/status requires it
                                 as an X-App-Key header; without it the live
                                 location is visible to anyone with the URL)
"""
import asyncio
import os
from datetime import datetime, timezone

import aiohttp
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pybyd import BydClient, BydConfig

VERSION = "1.0.0"
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
                hvac = {"temp_in_car": _temp(hv.temp_in_car),
                        "temp_out_car": _temp(hv.temp_out_car),
                        "ac_switch": _st(hv.ac_switch), "status": _st(hv.status),
                        "main_setting_temp": _temp(hv.main_setting_temp)}
            else:
                hvac = None
            return {
                "ok": True,
                "version": VERSION,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "vehicle": {
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


# Serve the static frontend (public/) — on Vercel this is also served as
# static files; locally uvicorn serves it from here.
app.mount("/", StaticFiles(directory="public", html=True), name="public")
