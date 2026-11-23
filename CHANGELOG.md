# BEYONDconnect changelog

## v1.3.16 — 23 Nov 2026

- Fixed the trip history and home going wrong overnight. When the car is asleep, BYD reports a 0 km odometer and a (0, 0) GPS fix (0, 0 is in the Gulf of Guinea — never a real location for this car), and those sentinel values were stored as real snapshots. The damage: live /api/trips returned home `[0.0, 0.0]` and phantom 23,728 km trips (a 0 km odometer followed by the real 23,728 km odometer reads as one 23,728 km "trip"). Fix, in two places: the poll writer now stores None for a 0 km odometer and for an invalid GPS fix (so new snapshots are clean at the source), and /api/trips nulls those sentinels out of stored snapshots before deriving anything (so the bad snapshots already in KV stop poisoning home, trips, sessions, SOH and range). `_home_location` and the trip place check also reject (0, 0) directly. Verified on synthetic data matching the live failure (Cikarang home cluster, the 68 km Cikarang → BSD drive, 400 BSD points interleaved with 200 asleep-sentinel snapshots): before the fix the raw data produced a 23,728 km trip; after it, home is the real BSD cluster and the only trip is the 68 km drive. Note: home now reads BSD (the densest real cluster — the car has been parked there ~17 h), not Cikarang; the "home should be Cikarang" question still needs a user-set home or a longer-window heuristic, it is not fixed by this.

## v1.3.15 — 23 Nov 2026

- When the car is charging, the hero card is now replaced by a charging scene (the old separate charge card below the hero — SVG silhouette, wall box and dashed cable — is gone). The scene uses Ray's own side-view Dolphin photo (public/dolphin-side.png, the smoothed-edges shot from the mockup, facing left), a big battery % with a count-up tween, a pulsing glowing progress bar directly below the car (the bar breathes and a bright shimmer sweeps along it), and a charger-type badge detected from the live charging power: AC Charger (≤ 22 kW), Fast Charger (≤ 60 kW), Ultra Fast Charger (above 60 kW — the Dolphin caps at 88 kW DC, so a >60 kW draw means a high-power DC station). The bar and badge change colour with the type (green / blue / purple). Stats are Power (kW), Charged (kWh — from the live charging session's integrated energy, falling back to the % gained since the charge started), Current (A — from power ÷ 220 V AC or 400 V DC) and Voltage (V). Liquid Glass throughout (translucent card, blur, top sheen), same 16 px spacing scale and 88% car width as the hero so nothing shifts when the scene swaps in. Note: dolphin-side.png is a binary, so it goes up via the GitHub web upload, not the text push.

## v1.3.14 — 22 Nov 2026

- The Tyres top-view car image is now Ray's own photo — the glass-roof top-down Dolphin (the second photo he sent, showing the seats through the panoramic roof), white background removed and edges smoothed with a Gaussian feather so the outline isn't jagged, resized to 397 px wide, replacing public/topview-atlantis.png. The tyre pressure callouts still point at the right wheels (verified in the rig). Note: the PNG is a binary, so it goes up via the GitHub web upload, not the text push — v1.3.13 (the density home fix below) was never pushed on its own, so it ships inside v1.3.14.
- Home detection, corrected (the v1.3.13 fix, shipping here). v1.3.12 changed the home calculation from a median to a most-common-grid-cell mode, but live verification showed it still returned BSD (`[-6.299905, 106.670625]`, 0.19 km from BSD, 53 km from Cikarang) — and the trip's end place read "Home" for BSD. Root cause: Cikarang's longitude 107.15 sits exactly on the 1-decimal grid boundary, so parked-car GPS jitter split home across two cells and BSD (stable, one cell) won the count; the 2-decimal grid had the same flaw. Home is now the densest 1 km spot across snapshots with no grid at all (the point with the most neighbours within 1 km, then the median point inside that spot). Verified on synthetic data matching the real drive (37 home snaps with jitter, 30 along the route, 26 in BSD): home lands 0.39 km from the real Cikarang home, inside the 0.5 km "Home" threshold.

## v1.3.12 — 22 Nov 2026

- Fixed the home detection that v1.3.11's "Home" label depends on. `_home_location` took the median of ALL snapshot latitudes and longitudes separately. After the Cikarang → BSD drive the snapshots split between the two ends plus the route, so the median landed mid-route — live /api/trips returned home `[-6.299905, 106.91652]`, ~26 km from the real home and ~26 km from BSD, so nothing was ever within 0.5 km of "home" and the "Home" label (and trip start/end "Home" places) never triggered. It now takes the most common ~1 km grid cell across snapshots and the median point inside it (the car is parked at home most of the time). Superseded by the density approach in v1.3.14 — the grid approach split home across a cell boundary and still returned BSD live.

- The location under the car name now updates. It was hardcoded to "Cikarang", so it still said that when the car was in BSD. Now it shows "Home" when the car is within 0.5 km of home (home location from /api/trips, now returned in the response) and the real area name when away, from a Nominatim (OpenStreetMap) reverse geocode of the car's GPS — "BSD City" for the BSD coordinates. Cached per ~1 km so a refresh or a drive doesn't re-fetch. The Location card's name uses the same label.
- The 6-digit BYD control PIN is now remembered on this device. It was stored in sessionStorage, which is cleared when the tab closes, so it had to be re-entered every session. It now lives in localStorage too and is auto-filled when you unlock with the app key — enter it once and you won't have to re-enter it for every action. It is stored only in this browser, never sent to the server (the app key still gates the app each session).

## v1.3.10 — 22 Nov 2026

- The scrollbar is hidden while scrolling. The page, the detail sheets and the trips table still scroll exactly as before — the bar just never renders (scrollbar-width: none + ::-webkit-scrollbar hidden, the same pattern the quick-action pills row already used).

## v1.3.9 — 22 Nov 2026

- Range calculation fixed: it now uses the car's own measured efficiency (recent 50 km, from the car's energy meter in the latest snapshot) instead of deriving efficiency from battery-% drops. The old way was wrong because the battery % is an integer — on a short trip a 1% rounding error swings the efficiency by a third. A single 18 km trip read 10.1 kWh/100km and produced a 599 km full range (563 km at 94%), while the car's own meter says 14.1 kWh/100km, giving 429 km full and 403 km at 94%. The trip-derived figure is now only a fallback when the car gives no efficiency reading.

## v1.3.8 — 22 Nov 2026

- Regenerative braking no longer counts as charging. The charging flag on a snapshot used to be set from charging_state alone, which reads 1 while regenerating (energy flowing back into the battery) — so a drive with heavy regen showed up as a charging session. Now a snapshot only counts as charging when the charging gun is actually plugged in (connect_state > 0, pyBYD's is_connected). The charging-session builder also drops any session where the car drove during it (odometer moved > 0.5 km), which cleans up false sessions from snapshots written before this fix. The live Charging tile uses the same rule, so it won't read "Charging" while braking; when the plug state is unknown it falls back to the old signals.

## v1.3.7 — 22 Nov 2026

- Trips no longer split when the car sits still briefly mid-drive. The trip detector closed a trip whenever the odometer didn't move for one poll (a traffic light, a quick stop), so a single drive showed up as two trips — e.g. a 1 km leg and a 10 km leg 2 minutes apart. Segments separated by under 10 minutes of standing still are now joined into one trip (distance, duration, battery and route all computed across the join). A real stop — parked 10+ minutes at a destination — still counts as a separate trip.

## v1.3.6 — 22 Nov 2026

- Vehicle tab is now bento tiles instead of two spec lists: a wide Battery hero tile (big %, green/red bar, "≈ 490 km range" subline), then Range, Range · your driving, Odometer, Efficiency · lifetime, Battery health · est., Capacity, and a wide Vehicle identity tile (Model / Nickname / VIN / Plate / Purchased as compact rows). Your-driving range and battery health show "Collecting…" until the background snapshots have enough history to estimate them.

## v1.3.5 — 22 Nov 2026

- Controls tab: four new functions — Find car (horn + lights), Flash lights, Windows and Trunk. Windows and Trunk are toggles: the tile shows Open/Closed from the car's live state, tap to open/close. Opening the windows vents them to a ~10% crack (BYD's native vent behaviour, not a full drop). Trunk open/close is gated on the car's config (functionNo 1020/1021) — if the Dolphin doesn't support it the app will say so instead of failing silently. All four need the 6-digit control PIN and ask for confirmation first.
- Controls fix: the Climate tile's big temperature was clipped at the tile edge (64px was too wide for the half-width tile) — now 52px and it fits. The −/+ steppers were white-on-white (the button colour came from the dark-mode text variable on the white "on" tile) — now dark on white with a visible border.

## v1.3.4 — 22 Nov 2026

- The PWA can't be zoomed or copied now: the viewport locks scaling (maximum-scale=1, user-scalable=no), text can't be selected and the long-press copy menu is blocked. Input fields (app key, PIN, tariff, battery kWh) still accept typing and pasting.

## v1.3.3 — 22 Nov 2026

- Tariff and Battery kWh are now in Settings (••• menu → Settings → Energy & cost) instead of on the Energy page. The Energy page is clean; the adjusters live behind a setting, and the cost tiles still use them.
- Charging history is on the Energy & cost tab: every charging session from the background snapshots is a card (date, time, place, energy, battery start → end, estimated cost).
- History cards expand into a detail sheet when tapped, like bydconnect.com. Charge Detail: Added to battery, Total cost, Energy Analysis (charger type inferred from peak power — ≤7 kW is a Granny charger — and peak power), a charging curve chart (power + battery over time, with average power), and additional details (odometer, price/kWh, start/end %). Trip details: distance, duration, consumption, efficiency, route, a GPS route map (Leaflet, start/end pins), average speed, compared to your average, battery and estimated cost. No Delete/Edit — sessions and trips are derived from the background snapshots, not stored records.
- Efficiency unit option (Settings → Energy & cost): kWh/100km or km/kWh. It applies everywhere — Energy tiles and bars, trip cards, trip detail (including the "compared to your average" comparison, which flips direction in km/kWh), the range estimate, and the Vehicle tab. Saved on this device; kWh/100km is the default. Cost per km is unchanged — it doesn't depend on the display unit.
- Trips tab: Export CSV and Clear history now live in a ••• menu at the top right of the Trips card, instead of two buttons at the bottom of the table.

## v1.3.2 — 22 Nov 2026

- New app icon, from Ray's photo: the orange-to-pink gradient rounded square with the white star glyph. It replaces the green B everywhere — login logo (shown as the rounded square, not a circle), favicon and Add to Home Screen icon. The icon was cropped from the photo (491×491) with its own corner radius kept and transparent corners, so it reads cleanly on light and dark.
- Removed three notes: the 6-digit PIN explainer on the Controls page, the "charging can't be stopped from the cloud" note, and the "no trips recorded yet" empty state (the Trips section is blank until a trip exists).
- Font sizing: the dashboard type was a step too big (card headings 20px, list rows 19px, tyre/tile values 24px, stat values 26px). Brought it down to iOS body scale — headings and rows 17px, tyre/tile values 20px, stat values 22px. The hero name, greeting and the big climate numbers are unchanged.

## v1.3.1 — 22 Nov 2026

- Login screen, like HomeView (measured from tuya-minimal.vercel.app): flat system background (no wallpaper, no glass card), round logo (logo.png), "Sign in to BEYONDconnect" in 26px bold (28px wrapped the longer name), 13px bold "App key" label, a 52px field with a 2px dark border and 16px radius, and a 52px black pill "Sign in" button (white with black text in dark mode). No subtext — the description and the car line under the button are gone. The flat background only applies while locked — the wallpaper comes back once you're in.
- New BEYONDconnect logo: a bold white B on a BYD-green gradient (light #00c853 → #007a33) with a soft top sheen, matching the app's glass. Round version (logo.png, 256px) is the login logo; rounded-square version (favicon.png 64px, apple-touch-icon.png 180px) is the favicon and the Add to Home Screen icon. NOTE: logo.png, favicon.png and apple-touch-icon.png are binaries — they need uploading via GitHub web when v1.3.1 is pushed (connector pushes text only).

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
