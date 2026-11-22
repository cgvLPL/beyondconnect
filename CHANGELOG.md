# BEYONDconnect changelog

## v1.3.0 — 22 Nov 2026

- A/C detail sheet: tap the Climate tile to open it — cabin view with driver/passenger seat ventilation (tap to cycle Off → Low → High), big temperature with a cold-to-hot slider, Turn on, Fast cooling (15 °C) and Quick heating (31 °C), plus circulation (Fresh / Recirculate), fan speed (1–7) and duration. While climate is running, temperature changes adjust the session without restarting it; circulation and fan changes re-send the full command.
- Climate start now sends circulation and fan speed to the car.
- Fixed all four things from your screenshots: the Location map is a real map again (the old embed shrank to a quarter of the card on phone screens — it's now an in-page map with a proper dark mode), tyre pressures no longer hide behind the car, the hero car sits with breathing room, and the Climate −/+ buttons stay inside their tile.
- Range is now estimated from your own charging and trip history (implied battery capacity ÷ the efficiency you actually drove at) — shown on the Battery card, the Energy page and the Vehicle tab. BYD's own range is still in the Vehicle tab.
- Trip history is detailed: each trip is a card with date, route (Home when it starts or ends there), time, duration, average speed, energy, efficiency, battery used and estimated cost.
- Wallpapers now show your actual photo: the old fixed-background CSS made iOS stretch the image over the whole page, so you only saw a slice of it. It's a fixed layer now.
- More from HomeView: the date under the greeting, and quick-action pills under it (Lock, Climate, Charge) that show the live state.
- Liquid Glass from HomeView (TuyaMinimal 2.92.02): the dock, pills, sheets and buttons now use HomeView's glass — a soft-light sheen across the top, and the dock adapts to the theme (white glass with dark icons in light mode, dark glass in dark mode) with a quiet fill on the active tab. Content cards lost their glass border and heavy shadow so they read as content; they stay frosted over your wallpaper. Switch knobs turn into a glass lens while you press them. (The gradient rim was tried and removed — plain 1px edge again.)

## v1.2.1 — 22 Nov 2026

- Fix: the Vehicle tab's system-health section read fields BYD doesn't report (`get_latest_config` is a feature list, not a health report), and the error broke the whole dashboard so the app opened to a black screen. The section is removed; the battery health estimate from charging/trip history stays. The app version now reads `version.json` so it can't drift from the release again.

## v1.2.0 — 22 Nov 2026

- Home screen redesigned: "Hey Ray!" greeting, dark hero card with your Atlantis Grey Dolphin photo, Battery + Last trip cards, full-bleed location map, icons-only dock.
- New Vehicle tab: VIN, plate, purchase date, odometer, battery health estimate from your charging sessions and trips.
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
