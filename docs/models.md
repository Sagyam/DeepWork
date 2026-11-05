# Realistic city: models plan

The city is moving from the low-poly kit (`ui/blender/city_kit.py`) to
realistic models, one building at a time. Models live in `ui/blender/real/`
(one module per model on a shared `lib.py`; `bun run models` writes the
git-ignored `ui/public/models/`), load in the app through
`ui/src/city/real.ts`, and replace the kit style they stand for; any model
that is missing falls back to the kit. Viewer: `/proto.html?model=c1` in the
dev server (see `docs/DEVELOPMENT.md`). In the app so far: A1, the prototype
brick block, C1, the clapboard farmhouse, S1, the main-street shop, C3,
the modern house, C4, the A-frame cabin, S3, the diner, and S4, the brick
factory; and the props round them (vehicles, trees, street
furniture, streets and the bridge; see "Props"). This file lists every model
the city needs, what each costs to draw, and the order to build them in. Go
through it section by section; tick or strike as decisions land.

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

Already written (`ui/blender/real/lib.py`, `ui/src/city/real.ts`), used by
every model after this one:

- Texture generators (numpy, seamless, with normal maps): brick, limestone,
  rusticated ashlar, granite, bitumen roof, wood staves, iron railing,
  grating, awning canvas, paving, asphalt, grime; with C1, painted
  clapboard, three-tab asphalt shingles and louvred shutters (near-white or
  grey, tinted per building in the app); with C3, smooth render and vertical
  timber battens (both tinted per building), roof gravel, a sedum roof and
  solar cells; with C4, hand-split cedar shakes and vertical
  tongue-and-groove boards (both pale, tinted per building); with S3,
  fluted stainless steel (brushed, with a roughness map) and moulded glass
  block (lit from behind at night); with S4, weathered corrugated sheet
  (galvanised, rust bleeding from the fixings and laps; tinted or painted
  per building), also for S6's canopy and sheds.
- Canvas textures drawn in the app: shop signs (eight names, a column and a
  row each) and, with S1, faded ghost-sign advertisements for party walls;
  with S3, diners' names in polished letters for the frieze; with S4, firms'
  names painted on a factory's brick, weathered.
- Lettering (with S3): `lib.letters` builds solid channel letters from
  Blender's bundled font (reproducible on any machine), `lib.neon` neon tubes
  along their outlines (`Mesh.tube`: a round tube along any path, also for
  pipe rails). Neon is coloured glass by day and lit at night.
- The piece pipeline: a model is drawn as a reference stack (ground storey,
  storeys, roof, extras such as a fence panel) so the AO bake sees each
  piece's neighbours, then split into one glTF node per piece with its base
  at the origin; one lightmap atlas per model. Window ids restart per piece
  and the app shifts them per storey and building, so stacked storeys get
  different rooms and lights.
- Geometry helpers: walls with openings and reveals, double-hung sash and
  French windows, sills, lintels with keystones, pediment hoods, sweeps for
  cornices, string courses and copings, dentils and modillions, quoins,
  railings with alpha-tested bars, balconies on corbels, fire escapes,
  shopfronts with stallriser, transom and sign fascia (`lib.shopfront`, any
  height and width, sign panel optional), awnings (`lib.awning`), recessed
  entrances with canopy, water tank, condensers, chimneys; with C3, modern
  glazing (`lib.glazing`: slim aluminium frames, fixed lights or sliding
  leaves, frameless where glass meets glass at a corner), the family for
  A3, A6 and the offices; with S4 (in `s4_factory.py`, to move into `lib`
  when a second model wants them), segmental arches with a ring of
  voussoirs and a stone key over any opening, steel windows of small panes
  with a hopper tilted open, ledged-and-braced doors, steel beams over wide
  openings, bulkhead lamps, and a round brick stack (bands, staples, a
  conductor, corbelled cap).
- Decals (`Model.decal`): paint on a wall, exported as `<piece>_decal` after
  the AO bake so the wall under it is not darkened.
- AO baked in Cycles on lightmap UVs.
- App materials (`real.ts`): PBR with weathering (rain streaks, splash,
  corner dirt), window glass that reflects the sky and shows a room behind
  it (walls, floor, furniture, curtains or blinds; lit at night; darkened and
  put out by damage; as wide as the window for glass walls), shop
  interiors, shop signs from an atlas of eight; glossy glass with sky
  reflections only, for rooflights and solar panels; with S3, a diner room
  (a booth at each window, sometimes with customers, the counter and its
  stools, the back bar, chequered floor) and polished metal that reflects the
  same sky as the glass; with S4, a works floor (whitewashed brick over a
  green dado, painted gangways, lathes and presses, a bench under the sill,
  truss ties and stanchions, the bands of north light overhead, lamps in
  enamel shades, a night shift in some) and north-light glazing that glows
  at night.
- Per-building variation by parameters: brick tint, shopfront colour and
  sign pair (A1); siding, shutter and door, and roof colours (C1); brick
  tint, shopfront and cornice colours, sign, ghost sign, an awning or none,
  two or three storeys (S1); render, cladding timber and aluminium colours
  (C3); board stain, shake, trim, door and deck-chair colours (C4); enamel
  colour, the two neon colours and the name (S3); brick tint, steelwork
  paint, door paint, roof sheet and the firm's name (S4).

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

## Decisions (2026-11-04)

- **One model per session**, Hamlet first: the kinds a hamlet builds
  (cottages and shops) before anything else. Order below under "Suggested
  order".
- **A model takes over its whole kit style** (A1 every classic apartment,
  C1 every classic cottage) until its siblings exist to take their own
  variants; one realistic look beats a mix of realistic and low-poly ones
  of the same kind.
- **Real-world sizes on today's 16 m lots:** each model has its own
  footprint and stand-back from the street (`DEFS` in `real.ts`); the
  plan's sizes still pick the floor count. A1 is 14 x 12 m and stands 1 m
  back on a paved lot; C1 is 10 x 11.8 m with its porch, 2 m back, behind a
  picket fence, with a drive; S1 is 9 x 11 m, 1 m back (its awning reaches
  over the pavement), with a walled service yard behind; C3 is 12.2 x 10.3 m
  with its cantilever and deck, 4 m back so the car fits on the drive in
  front of its garage, which leaves 1.7 m of garden behind the deck; C4 is
  8.6 x 12 m with its deck, steps and back landing, 1.5 m back, behind a
  post-and-rail fence among conifers, with a gravel drive; S3 is
  14.2 x 10.4 m with its vestibule steps and kitchen, 3.4 m back behind an
  asphalt forecourt with a car drawn up and its pylon sign at the corner,
  a fenced service yard behind; S4 is 13.5 x 10.4 m with its dock, boiler
  house and stack, 3 m back behind a concrete apron (a car nosed in by the
  stack, pallets by the dock steps, oil drums), a walled yard with a skip
  behind. Lots get resized with the master plan.
- **The app's lighting stays as it is** for now. It is tuned for the flat
  kit (strong hemisphere light), which makes the realistic models a little
  flatter than in the viewer; lowering their environment light changed
  nothing visible. Retune when the surroundings go realistic.

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
| C1 | Clapboard farmhouse | Gable roof, painted weatherboard, porch with posts, brick chimney, picket fence | cottage classic (gable) | **done** (2026-11-04): I-house, 3 bays, shutters, full porch, lean-to; 7.3 k triangles | 20% | P1 |
| C2 | Brick cottage | Hip roof in slate, bay window, stone sills, hedged garden | cottage classic (hip) | brick, stone | 10% | P1 |
| C3 | Modern house | Flat roofs, timber and render, big glazing, garage | cottage modern | **done** (2026-11-04): render ground storey with corner glazing and a timber-lined entrance recess, batten-clad upper storey cantilevered 1.2 m inside a white frame, garage with a batten door and sedum roof, deck; gravel roof with solar panels, rooflight, flue; pieces ground / upper / roof; 3.3 k triangles | 15% | P1 |
| C4 | A-frame cabin | Steep shingle roof to the ground, glazed gable, deck | cottage A-frame | **done** (2026-11-04): 60° A of cedar shakes down to 0.4 m, street gable glazed to the ridge in a timber grid with sliding doors onto a deck out from under the prow, ridge beam showing; shed dormer on the right slope, two rooflights and a stove pipe on the left; boarded back gable with door, landing and a woodpile; deck chairs; pieces body (to the loft floor) / roof; 3.5 k triangles | 10% | P1 |
| C5 | Stone cottage | Rubble-stone walls, gambrel roof with dormers, porch | cottage classic (gambrel) | new: fieldstone | 15% | P2 |
| C6 | Craftsman bungalow | Low hip, deep eaves with brackets, wide porch on tapered columns | | timber, stone | 10% | P2 |
| C7 | Half-timbered house | European: timber frame with render infill, steep tiled roof, jettied upper storey | | new: half-timber, clay tile | 15% | P2 |

### Shops (90 coins)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| S1 | Main-street shop | Two-storey brick, shop under flats, cornice, awning (a smaller sibling of the prototype) | shop classic | **done** (2026-11-04): 9 x 11 m, 1 m back; pieces ground / floor / awning / roof for 2-3 storeys; pressed-metal cornice, raised name panel, party wall with a ghost sign; 5.3 k triangles | 8% | P1 |
| S2 | Corner café | European: painted render, arched windows, oriel, umbrella tables | shop classic (café) | render | 12% | P1 |
| S3 | Diner | Stainless-steel railcar body, neon sign, booths in the windows | shop diner | **done** (2026-11-04): 1950s factory-built diner, 13.6 x 5 m body with rounded ends, fluted stainless with two enamel stripes, a window band with glass-block corners, an enamel frieze with the name, a barrel roof curving down over the ends; vestibule with steps and pipe rails; roof sign in channel letters with neon; brick kitchen behind; roadside pylon (EAT, an arrow of bulbs, a neon star); pieces body / roof; 7.7 k triangles | 18% | P1 |
| S4 | Brick factory | Sawtooth roof, tall smokestack, loading doors, steel windows | shop factory | **done** (2026-11-05): a late-Victorian machine works, 10.8 x 9 m shed under a three-bay sawtooth of corrugated sheet and north-light glazing, serrated coped gables to the street with a works clock and round vents; blue-brick plinth, pilasters, steel windows under segmental arches with stone keys, a frieze with the firm's name painted on; loading dock with buffers, steps and a canopy before ledged doors under a steel beam, an office door under a stone hood; lean-to boiler house, brick flue and a 17 m round stack; pieces body / roof; 10.7 k triangles | 18% | P1 |
| S5 | Corner store | One storey, roller shutters, painted signage, ice chest out front | | brick, metal | 10% | P2 |
| S6 | Filling station | Canopy on columns, pumps, small kiosk | | new: canopy, pumps | 15% | P2 |
| S7 | Market hall shop | European: arcaded ground floor, shops under the arches, stone above | | stone, render | 12% | P2 |

### Apartments (180 coins)

| ID | Model | Look | Replaces | Family | Effort | Priority |
|---|---|---|---|---|---|---|
| A1 | Pre-war brick block | Six storeys over shops, fire escape, water tank: **the prototype** | apartment classic (walk-up) | **done, in the app** (2026-11-04): pieces ground / first / floor a, b / last / roof, 3-7 storeys | done | P1 |
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
| Trees | ~~Six low-poly species~~ | **done** (2026-11-04): nine species, four shrubs, a hedge, light trees for the woods, lawns (see "Props") | 30% |
| Streets | ~~Flat roads, zebras, lamps~~ | **done** (2026-11-04): asphalt, kerbs, paving, lane marks, drains, manholes, LED street lights, hydrants, bins, benches, bus stops, traffic signals on a cycle | 25% |
| Automatic parks | Plaza / pond / football ground | Partly (2026-11-04): paving, lawns, lanterns, benches and trees are realistic; the fountain, bandstand, goals and stands are still the kit's | 30% |
| Vehicles | ~~Four cars, a bus~~ | **done** (2026-11-04): hatchback, saloon, estate, SUV, coupé, taxi, pickup, van, bus, box truck | 25% |
| People | One pedestrian | A few figures in varied clothes (small on screen, low detail) | 15% |
| Tower crane | Lattice crane | More detailed lattice (reuses the fire-escape strut code) | 10% |
| Bridge | ~~Truss bridge~~ | **done** (2026-11-04): riveted steel Pratt through truss | 10% |

### Props (2026-11-04)

The user found the realistic houses looked wrong next to the kit's cars,
trees, bushes, pavements and roads, so the reusable assets went realistic
in one session, with variations. Each is a props model (`PROPS` in
`real.ts`): one glb of named pieces at the origin, one AO atlas, loaded
with the buildings and replaced by the kit where missing. The viewer
lays any of them out: `/proto.html?props=cars` (see `docs/DEVELOPMENT.md`).

| Model | Module | Pieces | Triangles | How the app varies them |
|---|---|---|---|---|
| `cars` | `vehicles.py` | hatch, sedan, estate, suv, coupe, taxi, pickup, van, bus, truck | 9-10 k a car, 5-6 k bus and truck | clear-coat paint from `CAR_PAINTS` per car (instance colours in traffic); parked cars pick a body by how common it is |
| `trees` | `trees.py` | oak, maple, linden, birch, cherry, spruce, pine, poplar, young; bush, bush_wide, shrub, flowers, hedge; forest_a-e | 0.5-2 k a tree, ~170 a shrub, ~120 a wood tree | species by frequency, foliage tint (`FOLIAGE`), size from the kit's scale, turn; hedges stretched to length |
| `street` | `street.py` | lamp_led, lamp_heritage, lamp_park, signal_mast, signal_post, fence_panel, fence_rail, fence_iron, wall_brick, hydrant, bin, bench, bollard, busstop | 30-310 each | fence and wall runs stretched to fit (`fenceRun`); signals on two phases |
| `bridge` | `bridge.py` | bridge | 5.6 k | |

- **Vehicles** (rebuilt 2026-11-04: the first, lofted ones looked melted
  up close) are modelled the way car models are: a coarse cage of
  cross-sections at real cars' dimensions (underbody, rocker, side,
  shoulder, belt, roof rail, roof), Catmull-Clark subdivided with creases
  on the feature lines (shoulder, belt, cowl, back-glass base, nose and
  tail corners). Booleans cut the wheel arches, leaving the wells, and a
  pickup's bed. What sits on the skin is projected onto it by raycasts and
  laid a few millimetres above it: framed glass and black pillars, layered
  headlights with running-light strips, framed grilles with slats,
  intakes, tail lights, plates, panel seams and a fuel flap. Handles,
  mirrors, roof rails, arch cladding and multi-spoke wheels with brake
  discs and calipers are modelled on; edges over 40° shade hard
  (`Model.sharp`). Traffic (`traffic.ts`) draws them instanced, lamps lit
  at night; parked cars share their materials but stay dark. They are the
  heaviest props: LODs for traffic belong to "Last: performance".
- **Trees** grow branch tubes recursively from a seed and cluster leaf
  cards (alpha-tested, two-sided) round the twigs and along the outer
  branches, inside the crown's envelope. Leaf, needle, blossom and bloom
  cards are drawn procedurally (`leaf_textures`); the app bends the cards'
  normals out from each crown (`bendLeaves`) so it shades as one mass. The
  woods (`land.ts`) instance five light trees at the kit forest's sizes,
  on canopy textures whose gaps are filled with shade so mipmaps do not
  thin a far wood away. Lawns are a mown-grass texture mapped by world
  position (`groundMat`), as are the streets' asphalt and paving.
- **Street furniture**: kerb lamps reach over the road; from a town on,
  each block corner has a mast-arm or post signal on opposite phases of a
  30 s cycle (`setSignals`, with walk signals); every block gets a hydrant,
  bins and a bench, and from a city a bus stop. Yards use the fences and
  walls (back gardens close-board or post-and-rail, A1 and S1 brick walls,
  townhouse railings); parks the lanterns and benches.
- **Library additions**: `lib.blur` and `Model.export(..., smooth=)` blur
  the AO bake, whose sampling noise shows on glossy props lit mostly by the
  sky; a model module may carry its own `TEXTURES`, made with it.

Not done: the kit's people, crane and park pieces (fountain, bandstand,
goals, bleachers), and the terrain.

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
| P1 buildings (14 left, incl. 3 civic) | ~3 |
| P2 buildings (17) | ~3 |
| Building states | ~0.5 |
| Surroundings | ~2 |
| Last: performance | ~2 |
| Review and rework | ~1 |
| **Total** | **~15-16** |

## Suggested order

1. ~~Integration on the prototype: split it into pieces, add per-building
   variation, and load it in the real app next to the low-poly kit (drawn
   the simple way for now).~~ Done 2026-11-04, with C1.
2. The Hamlet, one model per session (decided 2026-11-04): ~~C1
   farmhouse~~, ~~S1 main-street shop~~, ~~C3 modern house~~, ~~C4 A-frame
   cabin~~, ~~S3 diner~~ (done 2026-11-04), ~~S4 brick factory~~ (done
   2026-11-05), then C2 brick cottage and S2 corner café for variety. After
   that the hamlet has no low-poly buildings left.
3. Progression v2 and the master plan (`docs/progression.md`): coins and
   the shop in the daemon, the designed layout in `plan.ts`. The plan decides which models are
   needed where, so it comes before most of them.
4. Download on first run, as soon as models leave the binary: pack,
   manifest, low-poly fallback.
5. One model per kind (C1, S1, A2, O1, L1) so a real mixed city can be seen.
6. The first civic landmarks (L5-L7) on their reserved ground.
7. The rest of P1, then building states.
8. Surroundings: streets, trees and terrain first, as they fill the most
   screen. Streets, trees, vehicles and the bridge done 2026-11-04 (see
   "Props"); terrain, people, the crane and the parks' pieces left.
9. P2 variety.
10. Last: performance.

## Open questions

Answered 2026-11-03: footprints (whatever makes sense), landmark ground
(reserved by the master plan), landmark size (the plan decides; coins pay).
The progression questions (animation vs instant purchase, the illusion of
control, the known holes) are in `docs/progression.md`.
