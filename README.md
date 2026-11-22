# BEYONDconnect — v1.0.0

A free, single-user clone of BYD Connect's live dashboard. No Google
sign-in, no subscription, no account system. It talks straight to BYD's
Indonesia server for one car (Ray's BYD Dolphin, Indonesia) using the
open-source [pyBYD](https://github.com/jkaberg/pyBYD) client.

## What v1 does (read-only)

- Live battery %, range, odometer, charging state, speed
- Live location on a map (OpenStreetMap + Google Maps link)
- Tyre pressures (psi / kPa / bar), doors, windows, locks
- Cabin / outside temperature, AC state, set temperature
- Energy: lifetime and recent-50 km consumption (kWh/100 km), 7-reading graph
- Cost: tariff (Rp/kWh, editable) → cost per km and per full charge
- Trips: snapshots saved in the browser while the page is open, with
  distance / energy / cost between snapshots, CSV export

## What v1 does NOT do (next)

- Remote lock / climate / charging controls — needs the 6-digit BYD
  control PIN, set in the BYD app first
- Background trip logging while the page is closed — needs a server
  that polls on a schedule plus a database
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
