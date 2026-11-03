# Progression: coins, the shop and the city plan

Ideas from 2026-11-03 for the realistic city (`docs/models.md`). Not built,
and not fully designed: there are known holes, to be fixed as we go. This
replaces "World model v2" (coins spent automatically by the app), which
was a misreading; the parts of it that still hold are kept below.

## The idea

The user earns coins by focusing and spends them in a shop on the next
upgrade of their settlement. The game decides what exactly gets built and
where. The user should feel the city is theirs, unique and growing because
of their effort, while the layout stays ours. Unlike Cities: Skylines,
there is no free placement: full control leads to bugs and to final
layouts that make no sense.

## Earning coins

- Focusing earns coins, per focused minute of a completed session.
- **Longer sessions earn a bonus.** Depth is the point of the app, so a
  50-minute session should be worth more than two 25-minute ones.
- **Day streaks earn a bonus.**
- A surrendered session earns nothing (as today, its time does not count).
- Coins are folded from the ledger like the rest of the world, never
  stored, so no client can edit a balance and past histories convert by
  themselves.

First guesses, to tune: 1 coin per minute; minutes past 50 in one session
earn 1.5; a 3+ day streak adds 25%.

## The shop

- Coins buy the next upgrade.
- **What can be bought depends on the settlement's level.** A hamlet cannot
  buy a skyscraper. Levels as today: Hamlet, Town, City, Metropolis
  (by focused hours, 10 / 50 / 200).
- **Locked items are teased.** Upgrades from higher levels show in the shop
  greyed out with a lock, or as a dark silhouette, and reveal themselves
  when the level is reached, so there is always something to work toward.
- During an upgrade the game decides what gets built and where: the user
  buys "an apartment block" or "a town square", never a spot on the map.

Price guesses (60 coins = 1 focused hour) carried over from v2:

| Upgrade | Coins | Unlocked at |
|---|---|---|
| Cottage | 45 | Hamlet |
| Shop | 90 | Hamlet |
| Apartment block | 180 | Town |
| Square or monument | 600 | Town |
| Office tower | 360 | City |
| Civic building | 1,200 | City |
| Landmark tower | 900 | Metropolis |
| Block landmark (cathedral, station, park, stadium) | 2,400 | Metropolis |

## The layout is ours

- One designed master plan: streets, districts, lots, the ground kept for
  squares, parks and landmarks. The user never places anything.
- When an upgrade is bought, the game picks its lot from the plan and the
  model that suits the street.
- **Density:** when a bigger building needs a spot that an older, smaller
  one holds, the old one is moved automatically to a new place (a cottage
  from the centre to a suburb) rather than torn down, so the user's first
  house survives as the city grows round it.

## Two circles not squared yet

The user will sort these later; noted here so they are not forgotten.

1. **The building animation vs instant purchase.** The construction site
   is meant to play while the user focuses. With purchases paid for at
   once, it may not be needed, or not for long.
2. **A perfect illusion of control.** The user should believe the city is
   unique and personal, growing because of their effort. Let them go wild
   and they make an ugly mess and lose interest. The question is how much
   real choice to give, and of what kind, so it feels like theirs without
   breaking the plan.

## Known holes

To fix as we go:

- What exactly the shop offers: a list of categories at each level, or a
  few concrete upgrades the game proposes each time.
- Penalties with purchases: what collapses on surrender if the build is
  bought instantly; whether repairs are bought in the shop or come first.
- Relocation: what happens when the plan has no free spot for a moved
  building, and how a move is shown.
- Balance: prices against the earning rate and bonuses, so each level takes
  about as long as it should (10 / 50 / 200 hours).
- Unlimited growth past the end of the designed plan.
- Converting today's cities (one building per session) when this lands.

## What stays from v2

- **Daemon / renderer split.** All policy stays in the daemon: coins,
  bonuses, prices, level gates, purchases, penalties, and the plan as a
  theme-agnostic sequence of slots (size class and place). The renderer
  decides what a slot looks like and where it is on the map. The shop UI is
  a view: it asks the daemon to buy; the daemon checks the balance and the
  level.
- **Penalties** keep their tiers (surrender severe, tamper major, refused
  root / clock jump / tunnel minor), to be re-priced in coins.
- **Fewer buildings.** With prices like the above, a city has ~80 buildings
  at the City level and a few hundred after a year, against up to 480 under
  one-building-per-session, which eases rendering.
