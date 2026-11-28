# BEYONDconnect changelog

## v1.12.1 — 28 Nov 2026

- Live-data corrections to v1.12.0 (found in the post-push live check against Ray's car): `epb` comes back -1 (unreported — pyBYD doesn't sentinel-strip it), which the Power tile rendered as "Park brake off"; negatives now render as no claim. `warnings.pwr` reads 2 on the parked car while power_system and every other flag read 0 — meaning unconfirmed (likely a state, not a fault), so it is excluded from the Warnings tile until pinned down (still present in the API payload). Live values otherwise healthy: tyres 38.8/38.1/37.4/36.5 psi (unit 2), all tyre statuses 0, power_state 1 (off), svs + rapid_leak unreported (null).

## v1.12.0 — 28 Nov 2026

- Tyres, warnings + power state on the Vehicle tab (Ray, 2026-11-28 07:59 WIB, picked from a pyBYD capability inventory). Backend maps power_gear, epb, ten warning flags (power_system, eps, esp, abs, svs, srs, ect, pwr, tpms, rapid_leak — 0 normal / >0 warning / null unreported), per-tyre status and tyre pressure unit into /api/status. Frontend: Tyres wide tile (2x2 pressures in the car's own unit — psi/bar/kPa by tyre_unit, flagged red per-tyre, TPMS/rapid-leak notes), Power tile (Off/Starting/On + park-brake state; BYD does not expose the P/R/N/D selector via this API — PowerGear is the power state), Warnings tile (All clear / N active + names, red when active). New wheel/power/alert glyphs in the v1.7.0 disc system. Verified: rig normal + injected-warning states (2 active: ABS + tyre pressure, RL flagged), zero JS errors; v1.11.0/v1.11.1 suites regression-clean. Note: the render() additions are block-scoped — a bare `const tp` collided with an existing declaration and killed the whole script (caught by the rig).

## v1.11.1 — 28 Nov 2026

- Battery health + driving range load fix (Ray, 2026-11-28 07:11 WIB: "can you fix the long load time for battery health and driving range"). Measured live: /api/status ~10.5 s (BYD cloud round trip, sometimes with a stale-session retry), /api/trips ~0.8 s (re-reads all 3000 KV snapshots and re-derives everything per request). Three fixes: (1) the frontend now fires /api/trips in parallel with /api/status instead of after it; (2) battery health + range paint instantly from the last visit's values (localStorage `beyondDerived`, alongside the v1.3.20 status cache) and refresh silently — including a real bug found on the way: `updateSohRow()` targeted a `#vehBatt` element that no longer exists, so fresh SOH only ever painted on the next status render; it now updates `#bSohVal`/`#bSohSub` directly (and `updateRangeTile` also paints `#bRangeYouVal`); (3) the backend caches the rate-independent derivation (trips + sessions without costs, SOH, range, home) in KV (`beyond:derived_cache`) under a fingerprint of its inputs (snapshot count + newest snapshot + home/merges/places + OCM-key presence) — repeat requests apply only the per-request rates and skip the 3000-snapshot read + derivation; `_capacity_estimates` is computed once per miss instead of twice. Responses carry `derived_cached`. Verified: 25 backend tests (fingerprint sensitivity, cost application, TestClient hit/miss/rate-change/new-snapshot/place-tag flows against a fake KV) + rig (tiles paint from cache with both APIs blocked; live values replace them; v1.11.0 provider flow regression clean; zero JS errors).

## v1.11.0 — 27 Nov 2026

- AC/DC charging rates + per-session fee (Ray, 2026-11-27 19:50 WIB: "research the rate of the public charger correctly for AC and DC", then "Yes, update the app rates to AC/DC + session fee"). Research (sourced): AC and DC energy cost the same max Rp 2.466,78/kWh in Indonesia (PLN publishes exactly this); DC costs more only via the regulated service fee (biaya layanan, DC only): Fast (>22–50 kW) max Rp 25.000/session, Ultra (>50 kW) max Rp 57.000/session excl. 11% PPN (Kepmen ESDM 182.K/2023) — boundary 50 kW, not 60. Backend: `_charging_sessions` records `peak_power_kw`; `_charge_type` classes a session DC when peak power > 22 kW (average-power fallback); `/api/trips` accepts `rate_<p>_ac`, `rate_<p>_dc`, `fee_<p>` per public provider (old `rate_<p>` still works as fallback) and returns `charge_type`, `peak_power_kw`, `rate_rp`, `fee_rp`, `est_cost_rp = round(kWh × rate) + fee`. Settings: each public provider gets AC rate, DC rate and session-fee inputs (stored as `settings.rates2`, migrated from the v1.10.0 flat rates); defaults from the research — SPKLU 2467/3600/0, Voltron 2875/3600/4000, Hyundai 2467/2467/3000, Other 2467/2467/0. Session cards show an AC/DC tag; the detail sheet shows "per kWh · DC" and "incl. Rp X fee" when a fee applies. Home keeps its single rate; trips/Energy tiles unchanged. Verified: 20 backend unit tests (classification boundaries, cost math, peak recording) + full mock rig flow (defaults, save → 22.4 kWh × 3400 = Rp 76.160, Voltron tag → 22.4 × 3600 + 4000 = Rp 84.640 with fee note, zero JS errors).

## v1.10.0 — 27 Nov 2026

- Per-provider charging rates (Ray, 2026-11-27 19:23–19:25 WIB: "make it so its possible to change the electricity rate based on the charger type", then "is it possible to detect automatically the provider of public charger since the rate differs"). The car/BYD API never reports the operator, so detection is by location: (1) a place Ray tagged on a session (KV `beyond:charge_places`, 150 m) wins; (2) within 0.5 km of home = Home; (3) nearest Open Charge Map charge point within 300 m, operator mapped to SPKLU/Voltron/Hyundai/Other (needs the free `OCM_API_KEY` env var; results cached in KV by 3-decimal coords); (4) Other public. Settings gains five rate inputs (Home default = old tariff 1700; public defaults Rp 2.467/kWh, SPKLU's published Rp 2.466,78). Session costs are computed server-side per provider (`rate_rp` returned per session); trips and the Energy tiles keep the home rate. The charge detail sheet shows the provider + how it was detected, the session's own Price/kWh, and a Change provider control (`POST /api/sessions/provider`, `/clear` to forget). SPKLU's per-session fast-charge service fee (≤Rp 25.000/57.000) is NOT modelled — per-kWh only. Verified: 19 backend unit tests (bucketing, precedence, OCM nearest/radius with mocked aiohttp) + mock rig. Live detection is unproven until Ray charges publicly (0 sessions so far) and sets an OCM key; tagging works without one.

## v1.9.1 — 27 Nov 2026

- Fixed the battery-health note on the Vehicle page (Ray, 2026-11-27 19:21 WIB: it said "Needs a charging session of 10%+ before it can calculate" yet a value already appeared at 3% charged). The 10% rule was enforced on the charging side — the live value (89.5% / 54.1 kWh) came from ONE trip, because trips using 5%+ of the battery over 5+ km feed the same capacity estimate; the note only told half the story. The note now names both paths, and the Battery health tile shows its basis ("54.1 kWh capacity · from 1 trip") from the `charge_sessions` / `trip_estimates` counts the API already returns, so a thin estimate is easy to spot. No math changed.

## v1.9.0 — 27 Nov 2026

- Pull down to refresh (Ray, 2026-11-27 19:17 WIB: "can you make it pull down to refresh"). Dragging down from the top of any page now reloads the car status — the same `load(true)` as menu → Refresh (/api/status + trips). A glass spinner pill follows the pull with damping (arrow rotates as you pull), spins while loading, then slides away. Guards: doesn't engage on the lock screen, while any sheet is open, mid-scroll, on horizontal drags, or while a refresh is already running. `overscroll-behavior-y:none` stops the browser's own pull-to-reload from competing. Verified on the mock rig with synthetic touch drags (indicator tracks the pull, release past the threshold triggers a status reload, short pull snaps back without refreshing).

## v1.8.0 — 27 Nov 2026

- Merge trips (Ray, 2026-11-27 17:28 WIB: "can you make it able to merge trips"). A drive the background logging split at a long stop (10+ min parked) can now be joined back into one trip: open a trip's detail sheet → Merge → "Merge with previous trip" / "Merge with next trip". Backend: `_derive_trips` gains `manual_joins` — segments whose start_time is in the set fold into the previous trip however long the stop was; each derived trip carries its `joins` list. The set is stored in KV (`beyond:trip_merges`) via `POST /api/trips/merge` {start_time} and removed via `POST /api/trips/unmerge` {start_times} ("Split back apart" in the sheet), so merges survive restarts and apply on every device. Merged trip cards show a Merged pill. Distance/energy/efficiency of a merged trip come from its first and last snapshots, same as any trip. Verified with unit tests on synthetic snapshots (no-join, single join, chained joins, join-on-first-trip and unknown-start no-ops) and on the mock rig.

## v1.7.1 — 27 Nov 2026

- Fixed commands failing with "byd_error: Request to /app/account/getAllListByUserId failed: Server disconnected" (Ray's screenshot, 2026-11-27 13:14 WIB). Root cause: `/api/control` had no recovery when the cached BYD session went stale — `get_vehicles()` disconnected, the handler returned the raw error, and the dead client stayed cached so the next command failed the same way. `/api/status` never showed this because it resets the client and retries once. Fix: `/api/control` now mirrors `/api/status` — the BYD work runs in a 2-attempt loop; on a generic exception it calls `_reset_client()` and retries once with a fresh login, returning the error only after the second failure (and the dead client is cleared either way). Genuine rejections still return immediately without retrying: wrong PIN (403, caught inline — avoids BYD lockout from repeated wrong PINs), unsupported endpoint, and remote-control errors. All actions are set-state (lock/unlock/climate/windows/trunk/charge-start), so a re-send after a mid-flight disconnect converges to the desired state. Verified with a mocked flaky client: disconnect-then-succeed returns 200 with one reset + one retry; persistent disconnect returns the same 502 `byd_error` after two attempts with no command dispatched. Live `/api/status` was healthy at diagnosis (49%, 23,827 km) — the session had already self-healed there, which is exactly the asymmetry this fix removes. Live command against the real car still needs Ray's PIN to prove end-to-end.

## v1.7.0 — 27 Nov 2026

- Icons, part 2 (Ray, 2026-11-27). (1) Every stat tile and list row gets a small hue disc with a white glyph, like TuyaMinimal's chips: Battery, Range, Odometer, Efficiency, Battery health and Capacity on Vehicle; Lifetime, Recent, Cost per km, Full charge on Energy; Added to battery, Total cost, Distance, Duration, Consumption in the trip and charge detail sheets; Inside, Outside, Set temp, AC; and the Front hood, Doors, Windows, Trunk rows. They are added by a small decorator keyed on the label, so tiles drawn later get them too. (2) No emoji or text symbols are left as icons: the close ✕, the menu ↓ ✦ › ✕, the location pin, the charger badge and the A/C MAX buttons are SVG, in the same stroke weights as the rest. (3) The Locks and Charging tiles and the hero lock button use the filled lock and bolt, matching the tab bar and the other tiles. The "Hey 👋" greeting is unchanged.

## v1.6.0 — 27 Nov 2026

- Icons like TuyaMinimal (Ray, 2026-11-27). (1) The tab bar uses the filled glyph set (fill + 1.2 stroke, 26 px) instead of outlines; (2) every control has a hue: Locks green, Climate blue, Charging yellow, Find car amber, Flash lights yellow, Windows teal, Trunk purple; (3) a tile's icon is that hue on a dark glass disc, and when the tile is on the disc fills with the hue from the centre and the glyph turns white (the fill, glyph flip and icon pop play when it toggles); (4) the Locked / Climate / Charge chips drop the emoji for a solid hue disc with a white glyph, and the lock glyph opens when the car is unlocked. Reduce Motion skips the fill animation.

## v1.5.0 — 27 Nov 2026

- Motion from TuyaMinimal (Ray, 2026-11-27). BEYONDconnect had almost no animation; it now uses the same vocabulary: (1) a springy press (scale .93–.96) on tiles, chips, buttons, the A/C controls and the tab bar; (2) pages slide in from the side they sit on in the tab order, 32 px + fade, .26 s; (3) control tiles bounce and brighten when they flip on/off, the icon pops and the status text fades in; the Controls chips pop too; (4) the A/C, settings and detail sheets spring up over a fading scrim, and the ••• menu opens with a small blur-in; (5) the tab bar's active pill is one element that slides and springs to the selected tab; (6) every segmented control (Fresh/Recirculate, Duration, efficiency unit) has a sliding thumb. All of it is off with Reduce Motion. No data or backend changes.

## v1.4.1 — 27 Nov 2026

- Control tiles (Ray, 2026-11-27). The big Climate tile now reads like TuyaMinimal's AC tile: temperature and the − / + buttons on top, name, state and the Start button pinned to the bottom, with room between the buttons and the label (they were touching). The − / + buttons are glass instead of black discs, and shrink slightly when pressed.

## v1.4.0 — 27 Nov 2026

- Liquid Glass like TuyaMinimal (Ray, 2026-11-27). Before, only the floating chrome (top buttons, chips, dock) was glass; the cards were near-black slabs, and with no wallpaper by default there was nothing for the glass to show. Now: (1) the Halftone wallpaper from TuyaMinimal is the default background (picker: Settings → Background → Halftone; anyone who already picked a background keeps it); (2) cards, Battery/Last trip tiles, the Location card, control tiles, trip cards, the hero card and the charging scene are translucent glass with a 22 px blur, a 1 px light edge, a lit top edge and a soft top sheen; (3) tiles/inputs/segmented controls inside a card are lighter nested glass; (4) the dock's active tab is a dark inset pill with an accent icon (lime in dark, green in light). The hero and charging scene stay dark glass in light mode because their text is light. Reduced-transparency users get solid cards.

## v1.3.22 — 24 Nov 2026

- Fixed the Last trip card on Home (Ray, 2026-11-24 07:17 WIB: "the last trip on the home screen is not updated"). Root cause: the backend returns trips newest-first (`_derive_trips` ends with `list(reversed(out))`), but the frontend picked `d.trips[d.trips.length-1]` — the last element, which is the OLDEST trip. So the card showed the 68 km drive from Nov 22 instead of the latest 6 km drive this morning (Nov 24 06:46 WIB). Fix: `_lastTrip` now takes `d.trips[0]` (newest). The trip history list itself was already correct (it renders newest first). Verified against live /api/trips: `trips[0]` is the 6 km Nov 24 06:46 WIB drive, `trips[-1]` is the 68 km Nov 22 drive.

## v1.3.21 — 24 Nov 2026

- The hero Dolphin blends into the black card (Ray, 2026-11-24 06:57 WIB). The car photo is a cutout, but its bright blue body and hard silhouette popped against the black card. Fix: a radial-gradient mask on `.herocard img.car` fades the car's outer edges (front, rear, wheels) into the card, plus `brightness(.88)` so the body sits quieter in the black. Iterated 5 times in the rig (the first masks were too subtle to see; the 4th was too strong on the front grille, the 5th keeps the face readable). Charging scene car (`dolphin-side.png`) untouched — follow-up if Ray wants it blended too.

## v1.3.20 — 24 Nov 2026

- Faster initial load (Ray, 2026-11-24 06:46 WIB). Measured live: the page shell loads in ~250 ms, but `/api/status` takes ~4.1 s because it calls BYD live (5 parallel BYD calls, each ~1 s) — so the dashboard sat blank for ~4 s. Fix: the last successful status is now cached in localStorage (`beyondStatus`, 24 h cap), and on startup the dashboard renders from that cache instantly and shows, while the live `/api/status` fetch runs in the background and re-renders with fresh data when it lands. The cached values are at most from the previous visit and are replaced within ~4 s.

## v1.3.19 — 23 Nov 2026

- The Locks tile padlock now animates (Ray's photo of a padlock): the shackle is its own SVG group with a CSS transition (transform-origin at the left hinge, spring easing). When the car is unlocked the shackle swings open 40°; when it locks it rotates back shut. Driven by the tile's existing `on` class (locked), so it follows the real lock state from the server.

## v1.3.18 — 23 Nov 2026

- Control icons are now the ones from Ray's picture (IMG_2189.png), extracted exactly by tracing the image: Flash lights is the headlight (was a household lightbulb), Trunk is the car rear with the lid opening and an up arrow (was a house), Find car is the car signalling with rays above it (was a map pin), and Windows is the car window with an up triangle (was a plain 2×2 grid). The four icons were traced from the PNG with OpenCV (threshold + contour trace, scaled to 24×24) and render as filled shapes with fill="currentColor", so they still adapt to dark/light mode. Locks and Charging kept their icons.

## v1.3.17 — 23 Nov 2026

- You can now set home yourself (v1.3.16 fixed the sentinel corruption, but the auto-detected home still read BSD once the car had sat there ~17 h — the densest snapshot cluster is wherever the car is parked now, not necessarily home). New `POST /api/set-home` (app-key gated) stores a {lat, lon, name} override in KV; `/api/trips` uses it for the home value and for every trip/charging "Home" place label, and reports `home_source` ("manual" / "auto") and `home_name`. `POST /api/clear-home` drops the override and goes back to auto-detection. In the app: open any trip's detail sheet and tap "Set start as home" or "Set end as home" (so the 68 km Cikarang → BSD drive can set home to Cikarang from its start), and Settings → Home location shows the current home with its source ("Set by you" / "Auto-detected") plus a Clear button when it's manual. The override is stored server-side, so it survives restarts and applies to every device. Verified: unit test on synthetic data (derived home = BSD, override = Cikarang → trip reads "Home → None"); rig test of the full flow (set from a trip, home flips to Cikarang, Clear reverts) pending before push.

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
