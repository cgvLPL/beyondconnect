# BEYONDconnect changelog

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
