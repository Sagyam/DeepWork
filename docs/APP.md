# The app

`deepwork-ui`: a Tauri 2 window over a Vite + TypeScript + three.js
frontend (`ui/`, built with bun). It shows the 3D city and the session HUD.
Looks follow [DESIGN.md](DESIGN.md), light and dark. Commands to run any of
this are in [DEVELOPMENT.md](DEVELOPMENT.md).

## Shell and data

- The Tauri shell has one command, `daemon`, which forwards a `Request` to
  the socket. No state, no policy; `Gate` is refused.
- The frontend polls `Status` every second and `World` every 5 s.
  `ui/src/proto.ts` mirrors `crates/proto` **by hand**: change both.
- Outside Tauri the page talks to a mock daemon (`mock.ts`, `mockcity.ts`, a
  small hand mirror of the daemon's fold).
- The realistic models are not in the binary: the app downloads a checked
  pack on first run (see [Model packs](#model-packs)).

## Screens

| Where | What |
|---|---|
| HUD | City card (level, progress, condition), the menu under it, the start card (timer / stopwatch, ring dial with 5-minute ticks and a drag handle, profile, stake, Start), the session card (timer, site progress, throttle stage, surrender with the phrase typed by hand) |
| Menu | Desk, Blueprints, Town hall, then Progress, Letters, sound, Settings. The desk button carries a dot while a need waits to be picked |
| Mayor's desk (`desk.ts`) | A panel from the menu: needs, buy plot, design pick, coins, paused sites, "What next?", today's goals, the two sets nearest done, items |
| Town hall | Street upgrades and renames, park decorations, every set begun |
| Letters (envelope) | The residents' letters, newest first, with a link to the building. An unread dot; what was read is kept in localStorage, and a first run starts with nothing unread |
| Shop | Blueprints for sale with pictures (`city/thumbs.ts`); later levels' in colour with a lock and the level that opens them |
| Deed card | A building's memory, rename, paid repair or a repair kit; hover shows a tag. Picking tests lot rectangles, not meshes |
| Settings sheet (cog) | Every `config.toml` key: session, site lists per profile, routines and skips, inverted mode, DNS, appearance, backup. Save sends the whole config; loosening shows the 24 h notice. About shows the build: CalVer, commit, commit and build times (`__BUILD__` from the Vite config) |
| Progress sheet (chart) | Stats (`stats.ts`, pure, tested) and the session log |
| Moments | Animated collapse, completion, damage, repair; fireworks and a card at level-up; near-miss "extend?" prompt; unseen events replayed on open; each with a sound (`sound.ts`, WebAudio, no files; mute by the menu) |

A renderer failure only loses the picture: the HUD keeps working.

## The city renderer (`ui/src/city/`)

| File | Role |
|---|---|
| `plan.ts` | The `World` as places, from the daemon's layout: a block shows once land in it is bought, parks by level; road classes per block side, street labels. `PUBLIC` and `NEED_LOOKS` pick models for public buildings. Pure, tested |
| `weather.ts` | What the weather is: nine kinds (`KINDS`), the day's by date and season, or a live report mapped by `fromReport()`. Pure, tested |
| `live.ts` | Live weather from Open-Meteo (on by default) for the time zone's city or a place picked in Settings, Appearance; localStorage only |
| `weatherfx.ts` | Drawing it: snow cover and wet puddles patched into every lit material, rain and snow, the cloud dome, lightning |
| `models.ts` | Builds buildings from model pieces, their yards, construction sites, damage, ruins (`shell()`), parks |
| `real.ts` | Loads the models, all or none; `DEFS` (size, set-back, the plan style drawn), `PROPS`, materials and shaders |
| `scene.ts` | Sky, sun by local time, shadows, bloom, camera; carries the performance work below |
| `terrain.ts`, `land.ts` | Hills, river, woods (instanced, with impostors from `impostor.ts`) |
| `roads.ts` | The lane graph, the road out of town, and car trips: routes, signals, parking. Pure, tested |
| `walks.ts` | Pedestrians: two walking lines per pavement, zebras on the walk phase. Pure, tested |
| `street.ts` | Where pavement furniture stands; the scene, cars and people share it |
| `traffic.ts` | Draws the cars (tilted on the hills) and people (limbs swung in the vertex shader) |
| `fx.ts` | Dust, sparks, fireworks |

### Weather

- **Live** by default: Open-Meteo every 15 minutes, coordinates rounded to ~1 km. The place is the city of the system time zone (`zoneCity()`) until the viewer names one.
- **By date** when turned off, with no place found, or after three hours without an answer: one weather a day, the same for everyone, with seasonal odds (`ODDS`); snow only in winter, storms mostly in summer.
- **Surfaces**: `weatherize()` chains onto each material's own patch in `prepare()`; snow settles on what faces up (`userData.snow` scales it), wet darkens, puddles mirror the sky cube and ring with rain.
- **Rain and snow** are one instanced draw each in a box ahead of the camera, moved in the vertex shader; drops are sized in pixels so far ones stay visible.
- **Clouds** are a dome in the sky scene, so they live in the background cube; they drift only on frames that draw anyway.
- Ambience only: weather rewards nothing.

### Street life

- **Cars make trips**: in by the road out of town, along the shortest way to a lot (pull in, park a while, back out), a bus stop, or out the other side.
- **Signals** run a cycle with an all-red walk phase (`signal()`, `walkLeft()` in `roads.ts`); the lenses follow it.
- **Cars yield**: gap to the car ahead, the crossing held until a tail clears it, stop for anyone on a zebra or a driveway.
- **People** keep to their line (inside one way, kerb side the other), each bent round furniture; cross only on the walk phase.
- `roads.test.ts` and `walks.test.ts` run minutes of traffic and check outlines for overlaps, red-light running and gridlock.

## Realistic models

Each model is a Python module in `ui/blender/real/` on the shared `lib.py`
(textures, geometry helpers, AO bake, export). `bun run models` writes the
git-ignored `ui/public/models/`. They are all the city draws: every style
in `STYLES` needs a model (`plan.test.ts` checks), and a missing one stops
the city with an error. Models of the same kind and style are siblings and
each building picks one by seed.

**Rules for every model**, so it stays cheap to draw:

- 20-40 k triangles a building, landmarks up to ~80 k.
- Materials from the shared library, at most ~25, named by role (`wall`,
  `trim`, `window`, ...).
- Stackable pieces (ground, storey, top, roof) where the kind has floors.
  Stand them apart in the bake (`GAP` in `l3_gothic.py`), or the piece above
  darkens the top of the one baked storey, and every floor repeats it.
- UV1 lightmap with baked AO; UV0 in metres; glass carries a window id for
  the interior shader.
- Real-world size; vary by parameters (colours, signs, names), never by copies.

### Catalogue

Status: **in** = in the app; blank = planned. `plan.rs` holds which ones
are blueprints and their prices.

| ID | Model | Fills | Module | Status |
|---|---|---|---|---|
| C1 | Clapboard farmhouse | cottage classic | `c1_farmhouse.py` | in |
| C2 | Brick cottage | cottage classic | `c2_cottage.py` | in |
| C3 | Modern house | cottage modern | `c3_modern.py` | in |
| C4 | A-frame cabin | cottage A-frame | `c4_aframe.py` | in |
| C5 | Stone cottage | cottage classic | `c5_stone.py` | in |
| C6 | Craftsman bungalow | cottage classic | `c6_bungalow.py` | in |
| C7 | Half-timbered house | cottage classic | `c7_timber.py` | in |
| C8 | Barn house | cottage modern | `c8_barn.py` | in |
| S1 | Main-street shop | shop classic | `s1_shop.py` | in |
| S2 | Corner café | shop classic | `s2_cafe.py` | in |
| S3 | Diner | shop diner | `s3_diner.py` | in |
| S4 | Brick factory | workshop | `s4_factory.py` | in |
| S5 | Department store | shop classic | `s5_store.py` | in |
| S6 | Tower brewery | workshop | `s6_brewery.py` | in |
| S7 | Corner store | shop classic | `s7_corner.py` | in |
| S8 | Filling station | shop diner | `s8_station.py` | in |
| S9 | Market hall | shop classic | `s9_market.py` | in |
| A1 | Pre-war brick block | apartment classic | `a1_apartment.py` | in |
| A2 | Brownstone row | apartment townhouse | `a2_brownstone.py` | in |
| A3 | Balcony block | apartment classic | `a3_balcony.py` | in |
| A4 | Art deco mansions | apartment classic | `a4_deco.py` | in |
| A5 | Parisian apartments | apartment classic | `a5_paris.py` | in |
| A6 | Modern apartments | apartment classic | `a6_modern.py` | in |
| A7 | Canal houses | apartment townhouse | `a7_canal.py` | in |
| O1 | Curtain-wall tower | office | `o1_tower.py` | in |
| O2 | Round glass tower | office | `o2_round.py` | in |
| O3 | Brutalist office | office | `o3_brutalist.py` | in |
| O4 | Stone office | office | `o4_stone.py` | in |
| O5 | Modernist slab | office | `o5_slab.py` | in |
| L1 | Art deco skyscraper | tower deco | `l1_deco.py` | in |
| L3 | Gothic skyscraper | tower deco | `l3_gothic.py` | in |
| L2 | Glass supertall | tower supertall | `l2_supertall.py` | in |
| L4 | Twisting tower | tower supertall | `l4_twist.py` | in |
| P1 | Substation | Hamlet / Town power | `p1_substation.py` | in |
| P2 | Power station | City power | `p2_power.py` | in |
| W2 | Pumping station | City water | `w2_pumping.py` | in |
| F1 | Fire station | fire station | `f1_fire.py` | in |
| E1 | School | school | `e1_school.py` | in |
| E2 | Police station | police | `e2_police.py` | in |
| E3 | Library | library | `e3_library.py` | in |
| H1 | Clinic | clinic | `h1_clinic.py` | in |
| H2 | Hospital | hospital | `h2_hospital.py` | in |
| L5 | City hall | city hall, on its half block | `l5_cityhall.py` | in |
| L6 | Town square | the square, on its half block (`square()` in `models.ts`) | code | in |
| L7-L13 | Monument, museum, theatre, cathedral, station, city park, stadium | landmark sites ([ROADMAP.md](ROADMAP.md#landmarks)) | | |

Props, each one glb of named pieces: `cars` (`vehicles.py`), `trees`,
`street`, `bridge`, `civic` (water tower, crane, scaffold, rubble, park
pieces, people). Water in the Hamlet and Town is the civic water tower.
Streets draw by class per block side: gravel lanes; tarmac, centre lines,
crossings and lamps from a street; trees from a boulevard; edge lines on
an avenue. Each block's north-east corner has a green sign naming its two
streets. Neighbourhood names float over their blocks, fading in as the
camera pulls back (`HOOD_NEAR`, `HOOD_FAR` in `scene.ts`). Unbought plots
carry a FOR SALE board. Park spots draw the
decorations bought for them (`SPOTS` in `models.ts`).

Signs that carry a name (S1 and S7's fascias; the café, diner and works friezes,
S6's painted wall, S8's canopy fascia, O4's carved frieze, S9's name panel; the office, L2 and S5 name panels and canopies; L1 and
L3's gilt names) show the building's own name: `NameSheet` in
`real.ts` paints each name into a shared sheet the first time a building
asks for it. A1's two shop signs are stock, by seed.

Plan parks and the square are laid out in code (`park()` and `utility()` in
`models.ts`) from these props on the shared ground textures (pave, ashlar,
gravel, grass).

### Model packs

Models ship as their own GitHub release, `models-<id>` (a prerelease, never
"latest"). `ui/src-tauri/models.json` lists each file's size and SHA-256
and is compiled into the app, which downloads into
`~/.local/share/deepwork/assets/<id>/`, refuses any mismatch, and shows
the HUD and the download, with no city, until the pack is whole. A GPU
without BC7 gets no city. The download is done by the app as the user,
never by the daemon. `<id>` hashes the file list, so unchanged models
download nothing. The pack's glbs are gzipped (`pack.ts`); the loader
inflates them, and reads a plain local build as it is. Publishing steps: [DEVELOPMENT.md](DEVELOPMENT.md#model-packs).

## Performance

Target: 30 fps for an end-game city on a weak iGPU (the host's Radeon
610M). `ui/town.html` (the showcase town) is where optimisations are tried
behind `&opt=N` before they move to `scene.ts`. What was learned:

- **Judge by the 1% low**, not the average. Hitches come from first-time
  shader compiles and texture uploads, so prewarm at load. Compare without a
  frame cap.
- **MSAA 4x at 1x scale** with alpha to coverage beats SMAA (stair-steps
  when stretched to a 1.5x screen, breaks thin railings).
- **The GPU limits, by pixels and the shadow pass.** Draw calls and
  triangles mattered little. The big wins: 1x render scale, a static
  shadow map (redrawn when the sun moves ~0.7° or a building changes), tree
  impostors past 150 m, the sky drawn once into a cube map, environment
  light on glossy materials only.
- **Moving things draw over a cached shadow map.** The static map is kept
  without what moves; while a building rises, falls or shakes, debris
  flies or a crane turns, each frame copies it back and draws only the
  movers (`shadows()` in `scene.ts`). Redrawing everything doubled those frames.
- **The ground is the dearest shader**: it draws after woods and buildings
  so the depth test skips what they cover, and samples grass or stone only
  where each shows.
- **Draw only when something changes.** A still city draws no frames; a
  hidden window none at all; an unfocused one ambient motion at `DIM_FPS`
  with traffic and auto-rotate stopped, moments still at full rate.
- **Leaves draw their depth first** (`leafPass()` in `scene.ts`): a cheap
  cut-out-only pass, then the lit leaves without depth writes, so each pixel
  is lit once, not once per leaf layer. Hamlet ~1.3 ms of ~20; nothing where
  impostors hold most trees. The pre-pass must repeat any vertex step
  (`userData.vertex`) or holes show the sky.
- **Shadow filter**: a fixed 2x2 grid of hardware-PCF taps (`shadow.ts`)
  looks like three's noisy 5-tap disc and saves ~1.5 ms; one tap shows
  jagged leaf shadows.
- **Quality presets** (`QUALITY` in `quality.ts`, chosen under Appearance,
  kept in the app): render scale, MSAA, shadow map and filter, bloom.
  Metropolis on the 610M: High ~50 ms GPU, Medium ~30, Low ~23. MSAA never
  goes below 2x: cut-out leaves rely on alpha to coverage.
- **Instance, don't merge** detailed models: merged geometry costs gigabytes.
- Texture bandwidth is not the limit here; BC7 compression (`scripts/textures.ts`)
  is for memory and download size. Share canvas sheets (`sheet()`), never
  one canvas texture per building.
- A shadow map or impostor atlas drawn once must wait for cut-out
  textures, or leaves vanish. Clamp brightness before bloom.
- Not worth it: lower anisotropic filtering, dropping normal maps, cheap
  far materials, geometry LODs for buildings, a sine-free hash in the
  ground's noise.

Open items are in [ROADMAP.md](ROADMAP.md#rendering).

## Decisions

- **3D city, generated assets.** A flat 2D skyline was tried and rejected:
  "nothing to be proud of, nothing to lose". Visuals must make loss hurt.
- **Realistic models only**, with no low-poly fallback: until the pack is there, no city.
- American and European styles mixed; real-world sizes per model.
- **Daylight from a warm sun and a sky hemisphere**, not a flat ambient: an
  ambient lights every face alike and flattened the models (`light()` in
  `scene.ts`). Late in the day the sun turns orange and the shade lilac;
  leaves let light through (`foliage()` in `real.ts`).
- Landmarks include civic buildings, squares, parks and monuments on half
  or whole blocks; the master plan reserves their ground.
- 30 fps for an end-game city on a weak iGPU is acceptable.
- **Long vehicles take no tight right turns** and park in no lot: a 12 m bus on a 4 m radius swung its tail into the oncoming lane.
- **Pedestrians walk fixed lines, not free steering**: per-person avoidance kept finding new overlaps and deadlocks.
- **Live weather finds the place from the time zone, not the IP**: locating by IP would hand the viewer's address to another service.
- **Tree impostors drop alpha to coverage in fog**: their half-covered edges showed as white outlines once fog greyed out the rest.
- Glbs gzipped, not meshopt: lossless meshopt shrank them less (31 MB to 18,
  gzip to 10) and its decoder needs WebAssembly, which the CSP refuses.
