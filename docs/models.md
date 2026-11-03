# Realistic city: models plan

The city is moving from the low-poly kit (`ui/blender/city_kit.py`) to
realistic models, one building at a time. The first one is done as a
prototype: a six-storey pre-war brick apartment block over two shops
(`ui/blender/proto_apartment.py`, viewer `ui/proto.html`, `bun run proto`
then `/proto.html?view=hero` in the dev server). This file lists every
model the city needs, what each costs to draw, and the order to build
them in. Go through it section by section; tick or strike as decisions land.

## How many buildings a city has

Replacing one building per session (ideas in `docs/progression.md`, not
built): focusing earns coins, coins buy upgrades in a shop gated by the
settlement's level, and the game decides what is built and where on one
designed master plan. Price guesses:

| Item | Coins | Focused hours |
|---|---|---|
| Cottage | 45 | 0.75 |
| Shop | 90 | 1.5 |
| Apartment block | 180 | 3 |
| Office tower | 360 | 6 |
| Square or monument (half block) | 600 | 10 |
| Landmark tower (lot) | 900 | 15 |
| Civic building (half block) | 1,200 | 20 |
| Block landmark (cathedral, station, park, stadium) | 2,400 | 40 |

| Tier (focused hours) | Built in that tier | City by its end |
|---|---|---|
| Hamlet (0-10 h) | ~8 cottages, 2 shops | ~10 buildings |
| Town (10-50 h) | ~10 cottages, 8 shops, 3 apartments, the town square | ~33 |
| City (50-200 h) | ~20 shops, 20 apartments, 6 offices, city hall | ~80 |
| Metropolis (200 h+, ~730 h a year at 2 h a day) | offices, towers, civic and block landmarks, more homes | a few hundred after a year |

Prices are first guesses. What this means for the models:

- **The plan picks the model for every lot**, so streets are composed, not
  random: a main street of shops, a row of brownstones, a downtown of
  towers. Each kind still needs several models so a street of one kind
  does not repeat, but no kind has to fill a whole city alone any more.
- **Far fewer buildings**: ~80 at City and a few hundred after a year,
  against 133-480 at 200 h before. That eases rendering (next section).

## Can an ordinary PC draw it?

Measured once to know the work is affordable. The optimisations it calls
for come last (see "Last: performance"); until then models go in drawn the
simple way, following the rules under "Rules for every model" so the late
work stays mechanical.

### Measured on this PC

Radeon 610M (the Ryzen 7700X's 2-CU integrated GPU, about the weakest GPU
still sold) in GPU Chromium, 1600 x 1000, pixel ratio 1. Each frame waits
for the GPU (a 1-pixel read-back), so these are real frame times; the
earlier "~90 fps uncapped" figures in PLAN.md counted frames queued faster
than the GPU drew them. "Browser CPU" is all Chromium processes together,
in cores, while rendering flat out.

| Scene | fps | ms / frame | JS ms / frame | Browser CPU | Triangles (incl. shadows) |
|---|---|---|---|---|---|
| Prototype, 1 building on its corner | 98 | 10.2 | 0.5 | 0.2 | 72 k |
| 25 full-detail buildings, instanced | 74 | 13.5 | 0.3 | 0.14 | 1.8 M |
| 100, instanced | 45 | 22.4 | 0.3 | 0.08 | 7.1 M |
| 250, instanced | 27 | 36.5 | 0.4 | 0.10 | 17.9 M |
| 100, one mesh per building | 39 | 25.5 | 6.2 | 0.52 | 7.1 M |
| 250, one mesh per building | 20 | 49 | 16.4 | 0.65 | 17.9 M |
| Current app, hamlet mock | 54 | 18.7 | 0.9 | 0.2 | |
| Current app, city mock | 42 | 23.6 | 2.6 | 0.28 | |
| Current app, metropolis mock (120 plots) | 33 | 30 | 7.4 | 0.48 | ~3.6 M |

How to rerun: `?count=N` (and `&draw=separate`) on `proto.html`; the
harness was a Playwright script driving `/usr/bin/chromium --headless=new
--use-angle=vulkan` with a GPU sync after every `requestAnimationFrame`.

### What the numbers say

- **The CPU is not the problem, as long as buildings are instanced.**
  Instanced, the JS side stays under half a millisecond a frame whatever
  the count (52 draw calls for 250 buildings), and the browser uses ~0.1 of
  a core, around 1% of an 8-core CPU. Drawn one mesh per building, the same
  250 buildings cost 12,000 draw calls and 16 ms of JS a frame: a whole
  core at 60 fps. Merging geometry (what `Parts` does today) is not an
  option for detailed models either: 1,000 merged 36 k-triangle buildings
  would be ~2-3 GB of vertex data. So: one instanced mesh per model, LOD
  and material.
- **The GPU is the limit.** A full-detail building costs ~0.1 ms of GPU
  time a frame on the 610M (72 k triangles with the shadow pass, ~700 M
  triangles a second). Fixed costs (sky, lighting, shadows, post at 1.6 MP)
  are ~10 ms. Full detail everywhere stays above 30 fps up to ~200
  buildings, then sinks.
- **Level of detail fixes it.** From the app's usual overview a building
  is 50-150 px tall; dentils, sashes and fire-escape treads are below a
  pixel. Three levels per model:

  | LOD | Triangles | What is kept | Used for |
  |---|---|---|---|
  | 0 | 20-40 k | everything | the nearest ~20 buildings |
  | 1 | 3-5 k | massing, cornices, balconies, signs; facades flat with baked detail (colour, normal and AO maps); the glass keeps its rooms (the interior shader works on flat panes) | the next ~200 |
  | 2 | 200-400 | a box with roof shape and a facade texture | everything further, and shadow casting past LOD 0 |

  1,000-building metropolis on the 610M, at the overview: 20 x 0.1 +
  200 x 0.012 + 780 x 0.0012 ≈ 5-6 ms for buildings, on top of the ~10 ms
  fixed cost and whatever terrain, trees and traffic cost. That is
  30-50 fps on the weakest GPU, before quality settings.

### Other hardware (scaled from the 610M by GPU throughput; not measured)

| GPU class | Examples | vs 610M | 1,000-building metropolis with LODs |
|---|---|---|---|
| Weak integrated | Radeon 610M, Intel UHD 620 | 1x | 30-50 fps, needs the Low preset on 1440p+ |
| Typical laptop integrated | Iris Xe, Radeon 680M / 780M | 4-8x | 60 fps |
| Entry discrete | GTX 1650, RX 6500 | 6-8x | 60 fps+ |
| Mid discrete | RTX 3060, RX 6700 | 20x+ | 60 fps+, even without LODs |

## What is reusable from the prototype

Already written, used by every model after this one:

- Texture generators (numpy, seamless, with normal maps): brick, limestone,
  rusticated ashlar, granite, bitumen roof, wood staves, iron railing,
  grating, awning canvas, paving, asphalt, grime.
- Geometry helpers: walls with openings and reveals, double-hung sash and
  French windows, sills, lintels with keystones, pediment hoods, sweeps for
  cornices, string courses and copings, dentils and modillions, quoins,
  railings with alpha-tested bars, balconies on corbels, fire escapes,
  shopfronts with stallriser, transom and sign fascia, awnings, recessed
  entrances with canopy, water tank, condensers, chimneys.
- AO baked in Cycles on lightmap UVs.
- Viewer materials: PBR with weathering (rain streaks, splash, corner dirt),
  window glass that reflects the sky and shows a room behind it (walls,
  floor, furniture, curtains or blinds; lit at night), shop interiors.

## Decisions (2026-11-03)

- **Style:** a mix of American and European, no preference between them.
  The master plan places them; no style districts are required.
- **Dimensions:** whatever makes sense for each model: real-world sizes for
  the type, not today's 9-10 m boxes. The master plan sizes lots to fit
  (wide suburban lots, narrow downtown ones), instead of the reverse.
- **Layout:** one fixed, designed city plan; nobody plans their own city,
  and old buildings move when bigger ones need their spot. Ground for squares,
  parks and landmarks is reserved in it from the start.
- **Currency:** focusing earns coins (bonuses for long sessions and
  streaks); coins buy upgrades in a level-gated shop; the game picks the
  building and the spot (see `docs/progression.md`).
- **Frame rate:** 30 fps for an end-game city on a weak iGPU is acceptable.
- **Landmarks** are not only towers: civic buildings,
  squares, parks and monuments too. These need more ground than a 16 m lot
  (see "Landmarks").
- **Models are downloaded on first run**, not built into the binary (see
  "Downloading the models").
- **Optimisation comes last:** LODs, instancing, pausing on inactivity, a
  frame cap, camera limits, presets and compression are one phase at the end.

## Rules for every model

So the last phase can optimise without remodelling:

- 20-40 k triangles for a whole building; landmarks up to ~80 k.
- Materials from the shared library only (brick, stone, render, glass,
  frame paint, ...), at most ~25 roles per model, named by role as today.
- Stackable pieces where the kind has a floor count: ground storey, typical
  storey, top storey, roof. Landmarks and open spaces are one piece.
- Lightmap UVs (UV1) with baked AO; UV0 in metres for tiling materials;
  glass panes carry (window id + u, v) for the interior shader.
- Variation through parameters (colours, signs, mirrored plans, roof gear),
  never through copies of the model.

## Downloading the models

- **Who downloads:** the app (`deepwork-ui`), as the user, never the root
  daemon. Clients stay untrusted views; the daemon does not care what the
  city looks like.
- **What:** one asset pack per release (models, KTX2 textures, a manifest of
  files with SHA-256 sums). The manifest's hash is compiled into the app, so
  a pack is checked before use and a tampered or stale pack is refused.
- **Where from:** a GitHub release asset (`Sagyam/DeepWork`), which has no
  bandwidth cap; Vercel (the landing site) does. Versioned by content hash,
  so an app update only fetches a new pack when the models changed.
- **Where to:** `~/.local/share/deepwork/assets/<hash>/`; old packs removed
  once the new one is verified.
- **Until it is there:** the current low-poly kit (4.6 MB) stays embedded as
  the fallback, so the app works offline and on first start; a small
  progress line in the city card while the pack downloads, and resume after
  a broken connection.
- **During a session:** GitHub is not throttled unless the user blocks it;
  if it is, the download waits for the session to end.
- **Packages:** the Arch / deb / rpm packages do not ship the pack either;
  the first run fetches it the same way.

## The buildings

Effort is in percent of a 5-hour usage window. The prototype took ~25%,
including the shared tooling above; a model that reuses its materials and
components should take 8-12%, one that needs a new material family 15-25%.
P1 replaces every style the city has today (plus the first civic landmarks);
P2 is variety, so one kind can fill a city.

### Cottages (45 coins)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| C1 | Clapboard farmhouse | Gable roof, painted weatherboard, porch with posts, brick chimney, picket fence | cottage classic (gable) | new: timber siding, shingles | 20% | P1 |
| C2 | Brick cottage | Hip roof in slate, bay window, stone sills, hedged garden | cottage classic (hip) | brick, stone | 10% | P1 |
| C3 | Modern house | Flat roofs, timber and render, big glazing, garage | cottage modern | new: render, glazing | 15% | P1 |
| C4 | A-frame cabin | Steep shingle roof to the ground, glazed gable, deck | cottage A-frame | timber | 10% | P1 |
| C5 | Stone cottage | Rubble-stone walls, gambrel roof with dormers, porch | cottage classic (gambrel) | new: fieldstone | 15% | P2 |
| C6 | Craftsman bungalow | Low hip, deep eaves with brackets, wide porch on tapered columns | | timber, stone | 10% | P2 |
| C7 | Half-timbered house | European: timber frame with render infill, steep tiled roof, jettied upper storey | | new: half-timber, clay tile | 15% | P2 |

### Shops (90 coins)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| S1 | Main-street shop | Two-storey brick, shop under flats, cornice, awning (a smaller sibling of the prototype) | shop classic | brick, stone | 8% | P1 |
| S2 | Corner café | European: painted render, arched windows, oriel, umbrella tables | shop classic (café) | render | 12% | P1 |
| S3 | Diner | Stainless-steel railcar body, neon sign, booths in the windows | shop diner | new: brushed metal, neon | 18% | P1 |
| S4 | Brick factory | Sawtooth roof, tall smokestack, loading doors, steel windows | shop factory | brick, new: steel sash, corrugated sheet | 18% | P1 |
| S5 | Corner store | One storey, roller shutters, painted signage, ice chest out front | | brick, metal | 10% | P2 |
| S6 | Filling station | Canopy on columns, pumps, small kiosk | | new: canopy, pumps | 15% | P2 |
| S7 | Market hall shop | European: arcaded ground floor, shops under the arches, stone above | | stone, render | 12% | P2 |

### Apartments (180 coins)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| A1 | Pre-war brick block | Six storeys over shops, fire escape, water tank: **the prototype** | apartment classic (walk-up) | done | done | P1 |
| A2 | Brownstone row | Three townhouses, stoops with iron railings, bay fronts | apartment townhouse | new: brownstone; brick | 12% | P1 |
| A3 | Balcony block | Rendered mid-century block, rows of balconies with glass rails | apartment classic (balconies) | render, glass | 12% | P1 |
| A4 | Art deco apartments | Buff brick, corner windows, deco spandrels and entrance | | brick, stone | 12% | P2 |
| A5 | Parisian block | European: cream stone, wrought-iron balconies, zinc mansard with dormers | | new: zinc roof | 15% | P2 |
| A6 | Modern apartments | Fibre-cement panels, deep loggias, timber soffits | | new: panels | 15% | P2 |

### Offices (360 coins)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| O1 | Curtain-wall tower | Blue-green glass, mullions, setback, plant room | office classic (curtain wall) | new: curtain wall | 18% | P1 |
| O2 | Round glass tower | Cylinder, horizontal fins, crown | office round | curtain wall | 12% | P1 |
| O3 | Brutalist office | Board-marked concrete, deep punched windows, pilotis | office classic (brutalist) | new: concrete | 15% | P1 |
| O4 | Stone office | Classical base, terracotta shaft, cornice (Chicago school) | | stone, new: terracotta | 15% | P2 |
| O5 | Modernist slab | Ribbon windows, white spandrels, roof canopy | office classic (fins) | curtain wall | 10% | P2 |

### Landmarks (600-2,400 coins)

Landmarks are the big purchases of the plan: towers, civic buildings,
squares, parks and monuments, each taking many sessions to pay for. Most
need more than a lot. Footprints:

| Size | Ground | Fits |
|---|---|---|
| Lot | 16 x 16 m | towers |
| Half block | 32 x 32 m (four lots) | city hall, museum, theatre, square, monument |
| Block | 64 x 32 m (all eight lots) | station, cathedral, park, stadium |

Decided: the master plan reserves their ground from the start (the town
square at the old crossroads, city hall facing it, the station at the
edge of downtown, ...), empty until the plan reaches them. A landmark's
size comes from the plan, not from a session.

Towers (replace today's landmarks):

| ID | Model | Look | Replaces | Size | Effort | Priority |
|---|---|---|---|---|---|---|
| L1 | Art deco skyscraper | Stone piers, setbacks, lit stepped crown, spire | landmark deco | lot | 25% | P1 |
| L2 | Glass supertall | Tapered glass, sky gardens, LED bands | landmark glass | lot | 20% | P1 |
| L3 | Twisting tower | Each storey turned, glass and white bands | landmark twist | lot | 15% | P1 |
| L4 | TV tower | Concrete shaft, observation pod, mast | landmark TV tower | lot | 15% | P1 |

Civic buildings, squares, parks and monuments (new):

| ID | Model | Look | Size | Effort | Priority |
|---|---|---|---|---|---|
| L5 | City hall | Classical front with columns and steps, dome or clock tower, flagpoles, forecourt | half block | 30% | P1 |
| L6 | Town square | Paving, a fountain, a statue on a plinth, trees, café tables, a bandstand or market stalls | half block | 20% | P1 |
| L7 | Monument | Triumphal arch or obelisk on a plaza, steps, lamps, flowerbeds | half block | 15% | P1 |
| L8 | Museum or library | Portico, broad steps, stone lions, banners | half block | 25% | P2 |
| L9 | Theatre | Marquee with bulbs, posters, ornate front, fly tower behind | half block | 25% | P2 |
| L10 | Cathedral | Gothic: twin towers, rose window, buttresses, slate roofs | block | 35% | P2 |
| L11 | Railway station | Stone front with a clock, iron-and-glass train shed, platforms | block | 35% | P2 |
| L12 | City park | Lawns, a lake with a boathouse, paths, avenue trees, a pavilion (needs the new trees) | block | 25% | P2 |
| L13 | Stadium | Bowl of stands, floodlights, pitch, entrance plaza | block | 30% | P2 |

The automatic parks every fourth cell stay as they are (plaza, pond park,
football ground; see "Not buildings"); earned parks and squares are larger
and grander, so the two read differently.

### States every building needs

| State | Today | Realistic version | Effort |
|---|---|---|---|
| Construction | Floors up to progress, scaffold, crane, blueprint | Same scheme with realistic scaffold, formwork, safety netting, site hoarding; landmarks fenced across their whole ground | 20% |
| Damage 1 | Darker, smoke | Soot streaks (grime shader), a few broken panes, smoke | 5% (shader) |
| Damage 2 | Lower ~3/4, no roof, fire | Broken top edge per piece, burnt interiors in the window shader, exposed floors; parks and squares scorched, statues toppled | 15% |
| Rubble | Heap of chunks | Brick / concrete heaps by family, bent beams, dust | 15% |
| Night | Window atlas lit | Done: the interior shader lights rooms | done |

## Not buildings, but they must match

Low-poly next to realistic buildings looks broken, so these follow in turn:

| Model | Today | Realistic version | Effort |
|---|---|---|---|
| Terrain | Faceted, flat-shaded hills, river, lake | Smooth terrain, grass / rock / soil textures, real water | 40% |
| Trees | Six low-poly species | 4-5 species with leaf cards, billboards far away | 30% |
| Streets | Flat roads, zebras, lamps | Asphalt, kerbs, paving, lane marks, drains, lamps, hydrants, bins, benches, bus stops, traffic lights | 25% |
| Automatic parks | Plaza / pond / football ground | Same three with paving, planting, a fountain, a bandstand, stands and floodlights | 30% |
| Vehicles | Four cars, a bus | Hatchback, saloon, van, taxi, bus, delivery truck | 25% |
| People | One pedestrian | A few figures in varied clothes (small on screen, low detail) | 15% |
| Tower crane | Lattice crane | More detailed lattice (reuses the fire-escape strut code) | 10% |
| Bridge | Truss bridge | Steel truss with deck and railings | 10% |

## Last: performance

Deferred to the end on purpose. Everything here is in the measurements
above; none of it changes how models look.

- [ ] **LODs:** LOD 1 (3-5 k triangles, facades flat with baked colour,
      normal and AO maps, glass keeps its rooms) and LOD 2 (200-400, a box
      with roof shape and facade texture), generated in Blender.
- [ ] **Instancing:** one InstancedMesh per piece, LOD and material in
      `models.ts`, instead of merging every building into shared meshes.
- [ ] **Pause on inactivity:** stop drawing when the window is hidden, on
      another workspace or minimised; ~5 fps when unfocused; draw only on
      change when nothing moves (no auto-rotate, no traffic in view).
- [ ] **Frame cap:** 30 fps by default.
- [ ] **Camera limits:** a minimum height and distance and a maximum tilt,
      so only a handful of buildings are ever close enough for LOD 0 and
      the far countryside stays out of view.
- [ ] **Quality presets** (Low / Medium / High): render scale, shadow-map
      size, LOD distances, MSAA, bloom. Low for weak iGPUs on 1440p and 4K
      screens, where pixel count costs more than triangles.
- [ ] **Texture compression:** KTX2 / Basis for the shared library (~250 MB
      of VRAM uncompressed, ~40-60 MB compressed); single-channel AO maps.
- [ ] **Geometry compression:** quantised meshes (meshopt), ~3 MB to ~1 MB a
      model; also shrinks the download.
- [ ] **Measure in the real window:** Tauri on Linux draws through WebKitGTK,
      whose WebGL is usually slower than Chromium's. Target: 30 fps for an
      end-game city on a Radeon 610M-class iGPU.

## Rough total

| Work | Windows (5 h each) |
|---|---|
| Integration: stackable pieces, variation, loading realistic models in the app | ~1 |
| Download on first run (pack, manifest, fallback) | ~0.5 |
| Progression v2 in the daemon: coins, bonuses, shop, level gates, penalties, UI | ~1.5 |
| Designing the master plan (layout, order, model per lot) and `plan.ts` | ~1 |
| P1 buildings (20 left, incl. 3 civic) | ~3 |
| P2 buildings (17) | ~3 |
| Building states | ~0.5 |
| Surroundings | ~2 |
| Last: performance | ~2 |
| Review and rework | ~1 |
| **Total** | **~15-16** |

## Suggested order

1. Integration on the prototype: split it into pieces, add per-building
   variation, and load it in the real app next to the low-poly kit (drawn
   the simple way for now).
2. Progression v2 and the master plan (`docs/progression.md`): coins and
   the shop in the daemon, the designed layout in `plan.ts`. The plan decides which models are
   needed where, so it comes before most of them.
3. Download on first run, as soon as models leave the binary: pack,
   manifest, low-poly fallback.
4. One model per kind (C1, S1, A2, O1, L1) so a real mixed city can be seen.
5. The first civic landmarks (L5-L7) on their reserved ground.
6. The rest of P1, then building states.
7. Surroundings: streets, trees and terrain first, as they fill the most
   screen.
8. P2 variety.
9. Last: performance.

## Open questions

Answered 2026-11-03: footprints (whatever makes sense), landmark ground
(reserved by the master plan), landmark size (the plan decides; coins pay).
The progression questions (animation vs instant purchase, the illusion of
control, the known holes) are in `docs/progression.md`.
