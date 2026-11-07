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

## Penalties and repairs

| Ledger event | In the city |
|---|---|
| Surrender (severe) | The session builds and earns nothing; fire damages the buildings nearest the site |
| `tamper` (major) | Earthquake damages a district |
| `escalation_denied`, `clock_jump`, `tunnel` (minor) | Light damage to the newest building |

Damage 3 is a ruin, which stands until repaired. Each completed session
repairs automatically (more with a streak). Coins are never taken. Bursts
within 10 min count once.

## Requests and events

The app and CLI only ask; the daemon checks with the same code the fold
uses. `Buy`, `Choose`, `Pause` (refused during a session) and `Rename` write
ledger events `blueprint_bought`, `need_chosen`, `site_paused`,
`building_renamed`. Backups carry them.

## Building memories

Each building keeps its story, folded from the sessions that built it:
name and address (renameable), sessions and focused time, start and finish,
damage and repairs, firsts. The app shows a hover tag and a click card
(the deed).

**Names** are dealt when a lot gets its design (`names.rs`), from the pile
for its class in `crates/daemon/names/`: the first name no other building
has, the design's own names first, so a diner gets a diner's name and its
sign shows it. Piles are append-only, like the plan's lots.
