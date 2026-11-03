# Realistic city: models plan

The city is moving from the low-poly kit (`ui/blender/city_kit.py`) to
realistic models, one building at a time. The first one is done as a
prototype: a six-storey pre-war brick apartment block over two shops
(`ui/blender/proto_apartment.py`, viewer `ui/proto.html`, `bun run proto`
then `/proto.html?view=hero` in the dev server). This file lists every
model the city needs, what each costs to draw, and the order to build
them in. Go through it section by section; tick or strike as decisions land.

## How many buildings a city has

One completed session adds one building (or rebuilds rubble). Its kind comes
from the session's length, not from the tier:

| Session | Grade | Kind | Size today (`shape()` in `plan.ts`) |
|---|---|---|---|
| < 25 min | 0 | cottage | 6-7.5 x 5.5-7 m, 1 storey |
| 25-49 min | 1 | shop | 8-9.5 x 7-9 m, 2-3 storeys (diner, factory 1) |
| 50-89 min | 2 | apartment | 8.5-9.8 m square, 4-7 storeys |
| 90-179 min | 3 | office | 9-10.2 m square, 9-14 storeys |
| 3 h+ | 4 | landmark | 10.4 m square, 18-25 storeys |

Tiers come from focused hours (10 / 50 / 200), so the building count at
each tier depends on how long sessions are:

| Tier (focused hours) | 25-min sessions | 50-min | 90-min |
|---|---|---|---|
| Hamlet (0-10 h) | up to 24 | up to 12 | up to 7 |
| Town (10-50 h) | 24-120 | 12-60 | 7-33 |
| City (50-200 h) | 120-480 | 60-240 | 33-133 |
| Metropolis (200 h+) | 480+ | 240+ | 133+ |

Metropolis never stops growing: two focused hours a day is ~730 h a year,
so a year's city holds 500-1,750 buildings. Two consequences shape the plan:

- **Each kind must fill a whole city by itself.** A Pomodoro user's
  metropolis is hundreds of shops; a 50-minute user's is apartments. Every
  kind needs enough models (5-6) plus per-building variation (brick and
  paint colours, frame colours, shop signs, floor counts, mirrored plans)
  that a street of one kind does not look copy-pasted.
- **Rendering must scale to thousands of buildings**, which rules out
  drawing every building at full detail (next section).

## Can an ordinary PC draw it?

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

### What it takes beyond LODs

- **Frame-rate policy.** This is a focus app that sits open for hours;
  drawing flat out pegs a laptop's iGPU (several watts, a warm fan). Cap at
  30 fps by default, drop to ~5 fps or stop when the window is unfocused,
  hidden or on another workspace, and redraw on change when nothing moves.
  This saves more battery than any modelling choice.
- **Quality presets** (Low / Medium / High): render scale, shadow-map size,
  LOD distances, MSAA, bloom. Low for weak iGPUs on 1440p and 4K screens,
  where pixel count costs more than triangles.
- **Texture compression.** The prototype's maps are ~19 MB of PNG. A shared
  material library of ~15 surfaces (colour, normal, roughness at 1024²) is
  ~250 MB of VRAM uncompressed; KTX2 / Basis brings it to ~40-60 MB.
  Per-model AO maps at 1024² single channel are ~1.4 MB each.
- **Geometry memory.** ~3 MB per model at full precision, ~1 MB quantised
  (meshopt); 30 models with LODs ≈ 40-100 MB. Instances cost nothing.
- **Install size.** Today the kit adds 4.6 MB to the binary. Thirty
  realistic models with compressed textures add ~60-90 MB.
- **The real window is WebKitGTK, not Chromium.** Tauri on Linux uses
  WebKitGTK, whose WebGL is usually slower. Every number above has to be
  checked in `deepwork-ui` itself before the design is fixed.

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

Still to build once, before models go into the app:

- [ ] Split models into stackable pieces (ground, typical storey, top storey,
      roof) so the plan's floor count still drives height.
- [ ] LOD 1 / LOD 2 generation (bake facades to textures in Blender).
- [ ] Instanced drawing in `models.ts` (one InstancedMesh per piece, LOD and
      material) instead of merging.
- [ ] KTX2 texture pipeline and a shared material library.
- [ ] Per-building variation: brick / render / paint / frame colours, shop
      names, mirrored plans, roof-gear seeds.
- [ ] Damage looks for realistic models (below).
- [ ] Frame-rate policy and quality presets.

## The buildings

Effort is in percent of a 5-hour usage window. The prototype took ~25%,
including the shared tooling above; a model that reuses its materials and
components should take 8-12%, one that needs a new material family 15-25%.
P1 replaces every style the city has today; P2 is variety, so one kind can
fill a city.

### Cottages (grade 0)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| C1 | Clapboard farmhouse | Gable roof, painted weatherboard, porch with posts, brick chimney, picket fence | cottage classic (gable) | new: timber siding, shingles | 20% | P1 |
| C2 | Brick cottage | Hip roof in slate, bay window, stone sills, hedged garden | cottage classic (hip) | brick, stone | 10% | P1 |
| C3 | Modern house | Flat roofs, timber and render, big glazing, garage | cottage modern | new: render, glazing | 15% | P1 |
| C4 | A-frame cabin | Steep shingle roof to the ground, glazed gable, deck | cottage A-frame | timber | 10% | P1 |
| C5 | Stone cottage | Rubble-stone walls, gambrel roof with dormers, porch | cottage classic (gambrel) | new: fieldstone | 15% | P2 |
| C6 | Craftsman bungalow | Low hip, deep eaves with brackets, wide porch on tapered columns | | timber, stone | 10% | P2 |

### Shops (grade 1)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| S1 | Main-street shop | Two-storey brick, shop under flats, cornice, awning (a smaller sibling of the prototype) | shop classic | brick, stone | 8% | P1 |
| S2 | Corner café | Painted render, arched windows, oriel, umbrella tables | shop classic (café) | render | 12% | P1 |
| S3 | Diner | Stainless-steel railcar body, neon sign, booths in the windows | shop diner | new: brushed metal, neon | 18% | P1 |
| S4 | Brick factory | Sawtooth roof, tall smokestack, loading doors, steel windows | shop factory | brick, new: steel sash, corrugated sheet | 18% | P1 |
| S5 | Corner store | One storey, roller shutters, painted signage, ice chest out front | | brick, metal | 10% | P2 |
| S6 | Filling station | Canopy on columns, pumps, small kiosk | | new: canopy, pumps | 15% | P2 |

### Apartments (grade 2)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| A1 | Pre-war brick block | Six storeys over shops, fire escape, water tank: **the prototype** | apartment classic (walk-up) | done | done | P1 |
| A2 | Brownstone row | Three townhouses, stoops with iron railings, bay fronts | apartment townhouse | new: brownstone; brick | 12% | P1 |
| A3 | Balcony block | Rendered mid-century block, rows of balconies with glass rails | apartment classic (balconies) | render, glass | 12% | P1 |
| A4 | Art deco apartments | Buff brick, corner windows, deco spandrels and entrance | | brick, stone | 12% | P2 |
| A5 | Parisian block | Cream stone, wrought-iron balconies, zinc mansard with dormers | | new: zinc roof | 15% | P2 |
| A6 | Modern apartments | Fibre-cement panels, deep loggias, timber soffits | | new: panels | 15% | P2 |

### Offices (grade 3)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| O1 | Curtain-wall tower | Blue-green glass, mullions, setback, plant room | office classic (curtain wall) | new: curtain wall | 18% | P1 |
| O2 | Round glass tower | Cylinder, horizontal fins, crown | office round | curtain wall | 12% | P1 |
| O3 | Brutalist office | Board-marked concrete, deep punched windows, pilotis | office classic (brutalist) | new: concrete | 15% | P1 |
| O4 | Stone office | Classical base, terracotta shaft, cornice (Chicago school) | | stone, new: terracotta | 15% | P2 |
| O5 | Modernist slab | Ribbon windows, white spandrels, roof canopy | office classic (fins) | curtain wall | 10% | P2 |

### Landmarks (grade 4)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| L1 | Art deco skyscraper | Stone piers, setbacks, lit stepped crown, spire | landmark deco | stone, new: metal crown | 25% | P1 |
| L2 | Glass supertall | Tapered glass, sky gardens, LED bands | landmark glass | curtain wall | 20% | P1 |
| L3 | Twisting tower | Each storey turned, glass and white bands | landmark twist | curtain wall | 15% | P1 |
| L4 | TV tower | Concrete shaft, observation pod, mast | landmark TV tower | concrete | 15% | P1 |
| L5 | Neo-gothic tower | Terracotta, pointed arches, pinnacles | | terracotta | 25% | P2 |

### States every building needs

| State | Today | Realistic version | Effort |
|---|---|---|---|
| Construction | Floors up to progress, scaffold, crane, blueprint | Same scheme with realistic scaffold, formwork, safety netting, site hoarding | 20% |
| Damage 1 | Darker, smoke | Soot streaks (grime shader), a few broken panes, smoke | 5% (shader) |
| Damage 2 | Lower ~3/4, no roof, fire | Broken top edge per piece, burnt interiors in the window shader, exposed floors | 15% |
| Rubble | Heap of chunks | Brick / concrete heaps by family, bent beams, dust | 15% |
| Night | Window atlas lit | Done: the interior shader lights rooms | done |

## Not buildings, but they must match

Low-poly next to realistic buildings looks broken, so these follow in turn:

| Model | Today | Realistic version | Effort |
|---|---|---|---|
| Terrain | Faceted, flat-shaded hills, river, lake | Smooth terrain, grass / rock / soil textures, real water | 40% |
| Trees | Six low-poly species | 4-5 species with leaf cards, billboards far away | 30% |
| Streets | Flat roads, zebras, lamps | Asphalt, kerbs, paving, lane marks, drains, lamps, hydrants, bins, benches, bus stops, traffic lights | 25% |
| Parks | Plaza / pond / football ground | Same three with paving, planting, a fountain, a bandstand, stands and floodlights | 30% |
| Vehicles | Four cars, a bus | Hatchback, saloon, van, taxi, bus, delivery truck | 25% |
| People | One pedestrian | A few figures in varied clothes (small on screen, low detail) | 15% |
| Tower crane | Lattice crane | More detailed lattice (reuses the fire-escape strut code) | 10% |
| Bridge | Truss bridge | Steel truss with deck and railings | 10% |

## Rough total

| Work | Windows (5 h each) |
|---|---|
| Shared tooling: pieces, LODs, instancing, KTX2, variation, presets | 2-3 |
| P1 buildings (17 left) | ~2.5 |
| P2 buildings (10) | ~1.5 |
| Building states | ~0.5 |
| Surroundings | ~2 |
| Review and rework | ~1 |
| **Total** | **~10** |

## Suggested order

1. Tooling first, on the prototype: split it into pieces, make its LODs,
   draw it instanced in the real app (WebKitGTK), measure, and settle the
   presets and the frame-rate policy. This decides whether the rest is
   affordable, before 27 more models depend on it.
2. One model per kind (S1, A2, O1, L1, C1) so a real mixed city can be seen.
3. The rest of P1, then building states.
4. Surroundings: streets, trees and terrain first, as they fill the most
   screen.
5. P2 variety.

## Open questions

- [ ] Where is the city? The prototype is pre-war American (brick, fire
      escape, water tank). Stay American, go European, or mix them, with
      older styles near the centre and glass towers further out?
- [ ] Sizes: should models keep today's footprints (9-10 m) or use the lot
      (16 m) more fully? The prototype is 14 x 12 m.
- [ ] Do landmarks have to be tall? A civic building (city hall with a dome,
      a station, a cathedral) could be the reward for a 3-hour session.
- [ ] Install size: ship all models in the binary (~60-90 MB more), or fetch
      them on first run?
- [ ] Minimum hardware: is 30 fps on a 610M-class iGPU at the Low preset
      good enough?
