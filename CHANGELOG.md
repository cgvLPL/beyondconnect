# BEYONDconnect changelog

## v1.2.0 — 22 Nov 2026

- Home screen redesigned: "Hey Ray!" greeting, dark hero card with your Atlantis Grey Dolphin photo, Battery + Last trip cards, full-bleed location map, icons-only dock.
- New Vehicle tab: VIN, plate, purchase date, odometer, battery health estimate from your charging sessions and trips, and 8 system health checks.
- Backgrounds: your five wallpapers (Ember, Dune, Nebula, Silk, Beams) with frosted glass cards; Control PIN moved into Settings.
- Controls rebuilt as HomeView-style tiles; the car is now shown in Atlantis Grey.
- Battery corrected to 60.48 kWh (Extended Range) — full-charge cost and trip energy now use the right size.
- Top bar removed; the ••• menu now sits next to the greeting.

## v1.1.0 — 22 Nov 2026

- Remote controls: lock / unlock, climate start/stop (temperature + duration), start charging. 6-digit BYD control PIN, entered once per tab, never stored.
- Background trip logging: the server polls the car every 5 min (GitHub Actions) into Vercel KV; Trips shows automatic trips with distance, energy and estimated cost.
- Page-based navigation with a floating glass bottom dock (Overview / Energy / Trips / Controls).
- Tyre pressure now shows your own top-down car photo.
- Liquid Glass restyle: frosted unlock card with pill PIN input, glass pill buttons, capsule on the active tab.
- Removed the "Updated …" line, the "What this is" card, the Trips explanation, the tyre placard note and "Fully electric".
- Charging can be started but not stopped from the app — BYD's cloud stop command doesn't work; stop with the key fob / door-handle double-unlock.

## v1.0.0 — 22 Nov 2026

- First release: live battery %, range, odometer, charging state, location, tyre pressures, doors/windows/locks, climate, energy and cost — straight from BYD's Indonesia server.
- No Google sign-in, no subscription, no account system. Single user, app-key protected.
- Liquid Glass design, OLED dark mode, charging scene with live power and ETA.
