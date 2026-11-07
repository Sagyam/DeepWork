# The game

Focus builds a city; giving in damages it. All rules live in the daemon
(`crates/daemon/src/plan.rs` for the plan, `world.rs` for the fold); this
file explains them. Numbers are constants in those files: read them there,
don't copy them here. Drawing is in [APP.md](APP.md).

## The one rule

**Every reward is paid for focused time. Nothing is paid for time spent in
the app.** A mechanic that rewards opening the app turns DeepWork into one
more distraction. Check every new idea against this.

So: no login bonuses or collect-every-N-hours timers; nothing to do in the
app during a session (only the site rising); bonuses for length stop at
3 h so a forgotten stopwatch doesn't pay; streaks always have a way back.

## The loop

The user is the mayor. Residents state the current level's **needs**
(houses, a shop, water, power, ...). The mayor picks a need; the game picks
the lot from a fixed master plan. A building rises only while the user
focuses, and each kind takes a fixed number of focused hours, so a cottage
is one sitting and a tower spans days. Focus also earns **coins**, which
buy **blueprints** (designs). When every need of a level is met the
settlement graduates: Hamlet → Town → City → Metropolis.

Whatever order the mayor picks, a finished level matches the plan; only
the facades (which blueprint) are the mayor's.

## Derived from the ledger

Nothing is stored. `world.rs` folds the ledger into a `World` on every
request, so clients can't edit progress, old histories convert themselves,
and the fold must stay **deterministic**. The plan only grows: lots are
appended, never reordered (`lot_ids_are_pinned`).

| | Coins | Build hours |
|---|---|---|
| Earned by | Completed sessions, with bonuses | Completed sessions, at face value |
| Spent on | Blueprints | The site under construction |
| On surrender | Nothing earned | Nothing built |

- **Coin bonuses** (`COINS_PER_HOUR`, `LENGTH_BANDS`, `STREAK_PCT_*`):
  longer sessions pay more per minute up to 3 h; a day streak adds a
  percentage; the first session after a missed day pays double (rested
  bonus). Bonuses never touch build hours, so a 25 h tower means 25 h.
- **Overflow**: hours past a finished building go to the next lot of the
  same need, else wait as crew hours for the next site.
- **Sites**: one active, up to 3 paused, half built.
- **Streak freeze**: one earned per 7 streak days (max 2), spent on a missed day.
- **Shiny buildings**: a seeded roll on completion; longer sessions raise the odds.

## Plan, needs and blueprints

- `NEEDS` in `plan.rs`: each level's needs, in the residents' words, each a
  fixed list of lots of one **kind** in one **district**.
- `BLUEPRINTS`: one design (= one model) per entry, with kind, allowed
  districts, level and price. Bought once, built any number of times. The
  farmhouse (`STARTER`) is free; the next level's are shown locked.
- Water, power and public buildings need no blueprint: the town builds them.
- Old ledgers with no decisions are built in the plan's default order.

## The ground

`layout.rs` lays the plan out: blocks on a grid by district, named streets
between them, and for each lot its slot, the street it fronts and its
number (odd north, even south). The Hamlet strings along Main Street, the
Town fills the far side, downtown grows south. Parks open by level. Lot
blocks group into named neighbourhoods (`NEIGHBOURHOODS`).

- **Land**: the first plot is free; every other one is bought, by hand
  (`BuyLand`). A site only starts on bought land; until then focus waits
  as crew hours.
- **Streets** start as gravel lanes and upgrade, for coins, to street,
  boulevard and avenue (`road_upgrade` in `economy.rs` sets price and
  level). A street whose every lot is built may be renamed by the mayor.
- **Decorations** stand on a park's five spots (none on the sports
  ground): trees, benches, fountain, statue, bandstand.

## Coins out

Prices are list price plus `WEALTH_PCT` of the coins held at the start of
the local day, so a pile costs more to spend but saving always catches up.
The opening balance, not the current one, so spending first never makes
the next thing cheaper. It applies to blueprints, land, repairs, streets
and decorations.

- **Paid repair**: a damaged building fixed now (`REPAIR_PER_DAMAGE`).
- **Stakes**: a countdown at least as long as the median of the last
  completed sessions (`stake_target`) may carry up to `STAKE_MAX` coins.
  Finishing pays the stake back twice; surrendering loses it.

## Goals and boxes

Three goals a day (`Goal` in `economy.rs`): two hours of focus, one
90-minute session, three sessions. Each pays one box, once a day. A box
holds a repair kit, hired help or, rarely, a master crew; the roll comes
from the session id, so it can't be rerolled, and every `PITY`-th box
without a rare one is rare. Help adds a share of a building's build time
to the active site; the deed shows it apart from focus.

**Sets**: every street with lots, and every neighbourhood, is a set.
Building its last lot pays one box, once (`STREET_RARE_PCT`,
`NEIGHBOURHOOD_RARE_PCT`); ruins and renames don't take it back.

## Letters

Families live in the homes (cottages and apartments): the one a house's
name gives ("The Hart house"), else one from `names/families.txt` by lot.
They write to the mayor when something reaches them (`letters.rs` words
it, `world.rs` decides when):

| Event | Who writes |
|---|---|
| A street upgraded | A family on it, else the nearest |
| A building whole again (bought, kit or session repairs) | Its own family, or the nearest |
| A park decoration | The nearest family |
| A public building opens | The nearest family |
| A set finished | A family on the street, else the nearest |

Letters are folded like the rest and pay nothing: reading one is not a reward.

## Penalties and repairs

| Ledger event | In the city |
|---|---|
| Surrender (severe) | The session builds and earns nothing; fire damages the buildings nearest the site |
| `tamper` (major) | Earthquake damages the fullest block |
| `escalation_denied`, `clock_jump`, `tunnel` (minor) | Light damage to the newest building |

Damage 3 is a ruin, which stands until repaired. Each completed session
repairs automatically (more with a streak). Coins are never taken. Bursts
within 10 min count once.

## Requests and events

The app and CLI only ask; the daemon checks with the same code the fold
uses. Decisions write ledger events, all refused during a session except
the renames: `blueprint_bought`, `need_chosen`, `site_paused`,
`building_renamed`, `land_bought`, `repair_bought`, `street_upgraded`,
`street_renamed`, `decorated`, `item_used`, and `stake_placed` with a
session's start. Backups carry them.

## Building memories

Each building keeps its story, folded from the sessions that built it:
name and address (renameable), sessions and focused time, start and finish,
damage and repairs, firsts. The app shows a hover tag and a click card
(the deed).

**Names** are dealt when a lot gets its design (`names.rs`), from the pile
for its class in `crates/daemon/names/`: the first name no other building
has, the design's own names first, so a diner gets a diner's name and its
sign shows it. Piles are append-only, like the plan's lots.
