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
| HUD | City card (level, progress, condition), the start card (timer / stopwatch, ring dial, profile, Start), the session card (timer, site progress, throttle stage, surrender with the phrase typed by hand) |
| Mayor's desk (`desk.ts`) | Needs, design pick, coins, paused sites, "What next?" |
| Shop | Blueprints for sale with pictures (`city/thumbs.ts`); later levels as silhouettes |
| Deed card | A building's memory, rename; hover shows a tag. Picking tests lot rectangles, not meshes |
| Settings sheet (cog) | Every `config.toml` key: session, site lists per profile, routines and skips, inverted mode, DNS, appearance, backup. Save sends the whole config; loosening shows the 24 h notice |
| Progress sheet (chart) | Stats (`stats.ts`, pure, tested) and the session log |
| Moments | Animated collapse, completion, damage, repair; fireworks and a card at level-up; near-miss "extend?" prompt; unseen events replayed on open |

A renderer failure only loses the picture: the HUD keeps working.

## The city renderer (`ui/src/city/`)

| File | Role |
|---|---|
| `plan.ts` | The `World` as places: lots, blocks, parks. `PUBLIC` and `NEED_LOOKS` pick models for public buildings. Pure, tested |
| `models.ts` | Builds a building from kit or realistic pieces; construction sites, damage, ruins (`shell()`) |
| `kit.ts` | Loads the low-poly kit (`public/city-kit.glb`, from `blender/city_kit.py`), the fallback for anything missing |
| `real.ts` | Loads realistic models; `DEFS` (size, set-back, kit style taken over), `PROPS`, materials and shaders |
| `scene.ts` | Sky, sun by local time, shadows, bloom, camera; carries the performance work below |
| `terrain.ts`, `land.ts` | Hills, river, woods (instanced, with impostors from `impostor.ts`) |
| `traffic.ts` | Cars and pedestrians |
| `fx.ts` | Dust, sparks, fireworks |

## Realistic models

Each model is a Python module in `ui/blender/real/` on the shared `lib.py`
(textures, geometry helpers, AO bake, export). `bun run models` writes the
git-ignored `ui/public/models/`. A model replaces a kit style; models of
the same kind and style are siblings and each building picks one by seed.

**Rules for every model**, so it stays cheap to draw:

- 20-40 k triangles a building, landmarks up to ~80 k.
- Materials from the shared library, at most ~25, named by role (`wall`,
  `trim`, `window`, ...).
- Stackable pieces (ground, storey, top, roof) where the kind has floors.
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
| C5-C7 | Stone cottage, craftsman bungalow, half-timbered house | cottage | | |
| S1 | Main-street shop | shop classic | `s1_shop.py` | in |
| S2 | Corner café | shop classic | `s2_cafe.py` | in |
| S3 | Diner | shop diner | `s3_diner.py` | in |
| S4 | Brick factory | workshop | `s4_factory.py` | in |
| S5-S7 | Corner store, filling station, market hall | shop | | |
| A1 | Pre-war brick block | apartment classic | `a1_apartment.py` | in |
| A2 | Brownstone row | apartment townhouse | `a2_brownstone.py` | in |
| A3 | Balcony block | apartment classic | `a3_balcony.py` | in |
| A4-A6 | Art deco, Parisian, modern apartments | apartment | | |
| O1 | Curtain-wall tower | office | `o1_tower.py` | in |
| O2, O3 | Round glass tower, brutalist office | office | | next |
| O4, O5 | Stone office, modernist slab | office | | |
| L1 | Art deco skyscraper | tower | `l1_deco.py` | in |
| L2-L4 | Glass supertall, twisting tower, TV tower | tower | | |
| P1 | Substation | Hamlet / Town power | `p1_substation.py` | in |
| P2 | Power station | City power | `p2_power.py` | in |
| W2 | Pumping station | City water | `w2_pumping.py` | in |
| F1 | Fire station | fire station | `f1_fire.py` | in |
| E1 | School | school | `e1_school.py` | in |
| E2 | Police station | police | `e2_police.py` | in |
| E3 | Library | library | `e3_library.py` | in |
| H1 | Clinic | clinic | `h1_clinic.py` | in |
| H2 | Hospital | hospital | `h2_hospital.py` | in |
| L5 | City hall | city hall (lot size until the plan has its half block) | `l5_cityhall.py` | in |
| L6-L13 | Town square, monument, museum, theatre, cathedral, station, city park, stadium | half or whole block | | |

Props, each one glb of named pieces: `cars` (`vehicles.py`), `trees`,
`street`, `bridge`, `civic` (water tower, crane, scaffold, rubble, park
pieces, people). Water in the Hamlet and Town is the civic water tower.

### Model packs

Models ship as their own GitHub release, `models-<id>` (a prerelease, never
"latest"). `ui/src-tauri/models.json` lists each file's size and SHA-256
and is compiled into the app, which downloads into
`~/.local/share/deepwork/assets/<id>/`, refuses any mismatch, and draws the
kit until the pack is whole. The download is done by the app as the user,
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
- **Realistic over low-poly**; the kit stays only as a fallback.
- American and European styles mixed; real-world sizes per model.
- **Daylight from a warm sun and a sky hemisphere**, not a flat ambient: an
  ambient lights every face alike and flattened the models (`light()` in
  `scene.ts`). Late in the day the sun turns orange and the shade lilac.
- Landmarks include civic buildings, squares, parks and monuments on half
  or whole blocks; the master plan reserves their ground.
- 30 fps for an end-game city on a weak iGPU is acceptable.
- Glbs gzipped, not meshopt: lossless meshopt shrank them less (31 MB to 18,
  gzip to 10) and its decoder needs WebAssembly, which the CSP refuses.
