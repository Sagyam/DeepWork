# Progression: coins, blueprints, residents' needs and the city plan

Design for the realistic city (`docs/models.md`), revised 2026-11-05 from
the user's brief. Not built. Replaces the 2026-11-03 shop idea ("coins buy
the next upgrade"); its daemon / renderer split and penalty tiers still
hold. Numbers are first guesses, to tune on real use.

## The loop in one paragraph

The user is the mayor. Residents say what the settlement needs right now
(houses, a shop, water, power). The mayor picks which need to work on
next; the game picks the lot from our master plan. A building rises only
while the user focuses, and each kind takes a set number of focused hours,
so a cottage goes up in one sitting and a tower over many. Focusing also
earns coins, which buy building designs (blueprints); a design, once owned,
can be built any number of times. When every need of a level is met, the
settlement graduates and new needs appear. Whatever order the mayor chose,
the finished level has exactly the plan's layout; only the facades, picked
from the mayor's blueprints, are theirs.

## Two currencies, one source

Focused time pays twice, and nothing is stored: both are folded from the
ledger like today's world, so no client can edit them and old histories
convert by themselves.

| | Coins | Build hours |
|---|---|---|
| Earned by | Focused time of completed sessions, with bonuses | Focused time of completed sessions, at face value (no bonuses) |
| Spent on | Blueprints | The building under construction |
| Lost on surrender | Nothing earned for that session | The session's work on the site (see "Penalties") |

Decided 2026-11-06: a third currency, diamonds, comes later (see
"Later: diamonds and loot boxes").

Bonuses touch coins only, so build times stay honest: a 20 h tower always
means 20 h of focus.

### Coins

- **Base:** 100 coins per focused hour, credited per minute.
- **Session length bonus:** minutes past 50 in one session earn 1.5x,
  past 90 earn 2x. Depth is the point of the app, so one 100-minute session
  beats two 50s (183 coins against 167).
- **Day streak bonus:** +10% per day of streak from day 3, capped at +50%
  (day 7). A streak day is a local day with at least one completed session
  of 25 min or more; it is kept until the end of the next day, as today.
- A surrendered session earns nothing.

## Blueprints

- A blueprint is one building design (one model: C1 farmhouse, A2
  brownstone row, ...). Bought once with coins, it can be built on every
  lot that takes it.
- **Gated by level and teased:** blueprints of the current level are for
  sale; the next level's show as locked silhouettes with their name, so
  there is always something to work toward.
- **Infrastructure is not a blueprint:** water, power and roads are needs
  without a design to buy (or a free one), so the first sessions are never
  stuck waiting for coins.
- **One starter blueprint is free** (the farmhouse), so the very first
  session builds something.

### Lots take a kind and size, not a model (decided 2026-11-06)

- Each lot names a **kind and size** ("cottage", "corner shop", "mid-rise
  apartments") and a **district**. The mayor fills it with any owned
  blueprint of that kind that the district allows; the district's list
  keeps the look coherent (no A-frame on main street, no farmhouse
  downtown).
- So streets, lots, sizes and the order of a need's lots stay ours; the
  facades are the mayor's. Buying a design is a real choice, and building
  it many times means something.
- A need's card shows the owned blueprints that fit, and the locked ones
  that would; with one fitting blueprint the choice is skipped.
- The renderer still varies each copy (colours, signs, yard), as today, so
  a street of the same design does not look cloned.

## Residents' needs

The plan is split by level. Each level is a set of **needs**, each need a
fixed, ordered list of plan lots:

```
Hamlet
  Housing shortage     4 homes      lots H1 H2 H3 H4   (1 h each)
  Small business       2 shops      lots H5 H6         (1.5 h each)
  Jobs                 1 workshop   lot  H7            (2 h)
  Water                1            lot  H8            (0.5 h)
  Electricity          1            lot  H9            (0.5 h)
                                                       = 10 h
```

- All of a level's needs are shown at once, each in the residents' words
  ("Four families share the old farmhouse"), with what is left, the build
  hours and whether the blueprint is owned.
- The mayor picks a need, never a lot. The game takes that need's next lot
  in its fixed order. Any interleaving of needs fills the same lots, so the
  level ends identical to the plan; only the in-between states differ. That
  is the illusion: real choice of order, none of layout.
- The mayor cannot build what nobody asked for.
- **Graduation is by needs, not hours:** a level ends when its needs are
  met. The level's hours are the sum of its build hours, so the plan sets
  the pace: Hamlet ~10 h, Town ~40 h more, City ~150 h more (the old
  10 / 50 / 200 thresholds). Metropolis is open-ended (see "Holes").
- **The plan only grows:** a later level never takes a lot from an earlier
  one, so nothing is moved or torn down. The Hamlet becomes the old quarter
  of the city and the first house survives. This drops the old
  "relocation" idea and its holes.

Need categories, roughly by level:

| Level | Needs |
|---|---|
| Hamlet | Housing, small business, jobs (workshop), water, electricity |
| Town | Apartments, shops and a café, school, clinic, fire station, a square, more houses |
| City | Offices, apartments, hospital, police, library, park, a civic landmark |
| Metropolis | Towers, a station, a stadium, a cathedral, landmark towers |

## Build time

Each kind of building has a fixed number of focused hours. First guesses:

| Kind | Build hours | Sessions at 50 min |
|---|---|---|
| Water, power | 0.5 | 1 |
| Cottage | 1 | 1-2 |
| Shop, café, diner | 1.5 | 2 |
| Workshop, factory | 2 | 3 |
| Apartment block | 4 | 5 |
| School, clinic, fire station | 5-6 | 6-7 |
| Office tower | 8 | 10 |
| Hospital, civic landmark | 12 | 15 |
| Skyscraper, block landmark | 20-30 | 25-35 |

`MAX_SESSION` is 6 h, so the biggest projects always span several
sessions and days. A site stays under construction between sessions, its
progress visible (scaffolding and crane growing with it).

- **One active site** takes the focused minutes of a session. The mayor can
  pause it and start another need; paused sites stay standing, half built.
- **Overflow is kept:** minutes left after a building completes go to the
  next need the mayor queued, or wait as idle crew hours for whatever is
  started next. So focusing with nothing chosen (or no blueprint yet) is
  never wasted.
- The app asks "What next?" when a site completes, and at session start if
  nothing is under construction.

## Penalties and repairs (decided 2026-11-06: automatic for now)

Penalty tiers stay (surrender severe, tamper major, refused root /
clock jump / tunnel minor) and so does today's automatic repair:

- **Surrender:** the active site loses that session's work, and fire does
  damage to the buildings nearest it.
- **Tamper:** an earthquake damages a district.
- **Minor:** light damage to the newest building.
- **Repair is automatic:** each completed session repairs damage, most
  damaged first, as `world.rs` does now (`1 + mins / 25` levels, doubled on
  a 3+ day streak), without spending build hours.
- **Nothing is lost for good:** a plan lot is never taken away, so a ruined
  building (damage 3) stays a ruin, scarred but standing, until repairs
  bring it back. Coins are never taken away; the loss is what the user sees
  in the city, and the time it takes to heal.
- Damage does not block graduation.

The user may revisit this to make repairs part of the game (repair needs
that cost build hours, or diamonds).

## Later: diamonds and loot boxes (idea, 2026-11-06, not designed)

- **Diamonds:** a rare currency that repairs damage at once or speeds up a
  construction.
- **Only from loot boxes**, and loot boxes **only from meeting daily streak
  goals**, never bought and never from coins. So diamonds reward
  consistency, the one thing coins' streak bonus touches lightly.
- Keep room for it now: loot boxes and diamonds fold from the ledger like
  everything else, opening a box is a daemon decision with a seeded result
  (deterministic from the ledger, so a client cannot reroll), and spending
  is a `diamonds_spent` event. Expediting must not make build hours a lie
  in the memories ("4 h focused, finished early with 2 diamonds").

## Building memories

Every finished building keeps its story, all folded from the sessions that
put minutes into it:

- Name and address: the plan gives a default name ("Hart's Bakery, 4 Mill
  Lane"); the mayor can rename it from its card (decided 2026-11-06). The
  address stays. The need it answered and the blueprint used.
- Started, finished, and how long it took in calendar time ("over 3 days").
- Focused hours, number of sessions, the longest one, and their kind:
  countdown or stopwatch, routine or manual, profile.
- Damage and repairs ("burned on 12 Nov after a surrender, rebuilt 14 Nov").
- Firsts: first building, longest session ever, built on a 7-day streak.

### How to show them

Recommended: **hover for a tag, click for the full card**, nothing always
on.

- **Hover:** a small tag over the building: name and one line ("Built
  7 Nov · 3 sessions · 2 h 10 m"). Cheap, it reads well in passing, and
  it makes the user want to look at their city.
- **Click:** a card in the design language (the "deed" or plaque): the
  whole story above, with the sessions as a small strip of bars, and the
  camera eases to the building.
- **Always on:** only the active site, with a small board showing
  progress ("2 h 40 m of 4 h"). Labels on every building would clutter the
  view and cost frame time.
- Later, if wanted: a "Memories" toggle that shows every tag at once, like
  a map overlay.

Picking stays cheap: lots are known rectangles, so the pointer is tested
against the ground plane and the lot under it, not the buildings' meshes.

## Daemon / renderer split

- **The daemon** owns the plan as data (levels, needs, lots with an id,
  size class, kind and build hours), coins, blueprints, sites, repairs and
  memories, all folded from the ledger. New ledger events:
  `blueprint_bought { id }`, `need_chosen { need }`, `site_paused { lot }`.
  `need_chosen` carries the blueprint picked; `building_renamed { lot,
  name }` holds a rename (trimmed, at most 40 characters, no control
  characters). The daemon checks the balance, the level, that the need is
  open and that the blueprint fits the lot; the app only asks.
- **The renderer** maps lot ids to places and models (`plan.ts`) and draws
  them. A test checks the two lists of lot ids agree.
- **Fold must be deterministic** and the plan versioned: changing the plan
  later must not reshuffle a user's existing city (lots are only ever
  appended).

## Decided

- 2026-11-06: lots take a kind and size, the mayor picks the design;
  repairs stay automatic for now; buildings get a default name the mayor
  can change; diamonds and loot boxes come later.

## Holes, to fix as we go

- Metropolis and beyond: open-ended needs in expansion districts once the
  designed plan runs out.
- Balance: blueprint prices against coins per level, so the mayor can
  always afford the next needed design (Hamlet: ~1,000 coins earned
  against ~1,000 of blueprints).
- Converting today's cities: past sessions have no `need_chosen` events,
  so the fold fills needs in the plan's default order with their hours,
  once, and memories come from the sessions that fall in each build.
- Paused sites: limit how many may stand half built (say 3).
