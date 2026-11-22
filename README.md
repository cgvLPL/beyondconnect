# BEYONDconnect — v1.1.0

A free, single-user clone of BYD Connect's live dashboard. No Google
sign-in, no subscription, no account system. It talks straight to BYD's
Indonesia server for one car (Ray's BYD Dolphin, Indonesia) using the
open-source [pyBYD](https://github.com/jkaberg/pyBYD) client.

## What it does

- Live battery %, range, odometer, charging state, speed
- Live location on a map (OpenStreetMap + Google Maps link)
- Tyre pressures (psi / kPa / bar), doors, windows, locks
- Cabin / outside temperature, AC state, set temperature
- Energy: lifetime and recent-50 km consumption (kWh/100 km), 7-reading graph
- Cost: tariff (Rp/kWh, editable) → cost per km and per full charge
- Trips: snapshots saved in the browser while the page is open, with
  distance / energy / cost between snapshots, CSV export

## v1.1 — remote controls

The Controls card locks/unlocks, starts/stops climate (temperature +
duration), and starts charging. Every action asks for confirmation.
The 6-digit BYD control PIN (set in the BYD app: vehicle settings →
remote control password) is entered once per tab — it lives in
sessionStorage only and is sent with each command; the server never
stores or logs it. `POST /api/control` takes
`{action, pin, temperature?, duration_min?}` and needs the app key
when `BEYOND_PASSWORD` is set.

Honest limit: **charging can be started but not stopped from here.**
BYD's cloud stop-charge call is a verified no-op (it returns success
but the car keeps charging — pyBYD documents this and refuses to send
it). Stop a charge with the key fob / door-handle double-unlock.

## v1.1 — background trip logging

`/api/poll` snapshots odometer / battery / GPS into Vercel KV, and
`/api/trips` derives trips from those snapshots (start/end, distance,
energy, estimated cost). The Trips section shows automatic trips first
and keeps the browser-local history, CSV export and clear button.

Polling, two parts:

1. **Vercel Cron** (in `vercel.json`, once a day at 01:00 UTC) — a
   heartbeat only. Vercel's Hobby plan allows cron jobs once per day;
   a `*/5` expression would fail the deployment, so the 5-minute
   polling is done by part 2.
2. **GitHub Actions** (`.github/workflows/poll.yml`, every 5 min) —
   calls `/api/poll` with the `X-App-Key` header. No new account
   needed. Setup: repo → Settings → Secrets and variables → Actions →
   new secret `BEYOND_PASSWORD` with the same value as the Vercel
   env var. (Note: the GitHub connector can't write `.github/`
   workflow files — add this file through the GitHub web UI if the
   push leaves it out.)

Storage setup (once): Vercel dashboard → Storage → Create Database →
KV → create a store → link it to the `beyondconnect` project. That
sets `KV_REST_API_URL` / `KV_REST_API_TOKEN` automatically. Without
a linked store, `/api/poll` returns `kv_not_configured` and the
dashboard falls back to browser-local trips. Optional env vars:
`CRON_SECRET` (Vercel Cron auth), `TARIFF_RPKWH` (default 1700),
`BYD_BATTERY_KWH` (default 44.9).

## What it does NOT do (next)

- ABRP live-data sync, battery-health trends, multi-car garage

## Setup (Vercel)

1. Create a Vercel project from this repo.
2. Set these environment variables in Vercel (never in the repo):
   - `BYD_USERNAME` — BYD account email
   - `BYD_PASSWORD` — BYD account password
   - `BEYOND_PASSWORD` — optional app key; if set, the dashboard asks
     for it once per tab (stored in sessionStorage only). **Set this** —
     without it, anyone with the URL can see the car's live location.
   - `BYD_COUNTRY_CODE` — `ID` (default)
   - `BYD_TIME_ZONE` — `Asia/Jakarta` (default)
   - `BYD_BASE_URL` — `https://dilinkappoversea-id.byd.auto` (default)
3. Deploy. No build step.

Note: signing in with the main BYD account signs the BYD app on your
phone out. Use a second BYD account shared to the car for this app if
you want the phone app to stay signed in.

## Local run

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
BYD_USERNAME=you@example.com BYD_PASSWORD=... \
BYD_COUNTRY_CODE=ID BYD_TIME_ZONE=Asia/Jakarta \
BYD_BASE_URL=https://dilinkappoversea-id.byd.auto \
venv/bin/uvicorn app:app --port 8000
```

Open http://127.0.0.1:8000

## Why the Indonesia server matters

BYD has a separate node per region. Indonesia is
`dilinkappoversea-id.byd.auto` — not Singapore (`-sg`) and not Europe
(`-eu`). Pointing at the wrong node returns "Wrong email or password"
(code 3008) even with correct credentials. That was the whole login
mystery on 2026-11-22: bydconnect.com uses the ID node, pyBYD's
default is EU.

## Disclaimer

BYD does not publish this API. It can change without notice. This is
a clean-room re-implementation for personal use, not affiliated with
BYD or BYD Connect.
