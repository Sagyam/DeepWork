# Hooks: game psychology pointed at focus

Ideas from 2026-11-06, not built. Gacha and free-to-play games are very good
at making people come back; DeepWork borrows their tactics without the
money, to pull the user into focus sessions. Builds on
`docs/progression.md` (coins, blueprints, residents' needs, build hours,
diamonds and loot boxes).

## The rule

**Every reward is paid for focused time. Nothing is paid for time spent in
the app.**

A mobile game wants eyes on the game; DeepWork wants the city to pull the
user into a session and then get out of the way. A hook that rewards
opening the app turns DeepWork into one more distraction. Every idea below
is checked against this rule.

## Worth adding

### Variable rewards (the slot machine)

- **Shiny buildings.** When a building completes, a small chance it comes
  out rare: a golden-hour facade, a neon sign, a rooftop garden, a statue
  in the yard. Longer sessions raise the odds. The surprise is the result
  of focusing itself, so the reward and the behaviour are the same thing.
  The best fit of the lot.
- **Pity counter on loot boxes.** As in gacha games, a rare item is
  guaranteed after N boxes without one, so bad luck never becomes a reason
  to quit. Show the counter ("rare in 3 boxes at most").
- **Rarity tiers in boxes.** Common: diamonds. Rare: a variant of a blueprint
  the user owns. Epic: a decoration (fountain, clock tower, statue).
  Legendary: a landmark that cannot be got any other way.

### Loss aversion (the app already runs on it)

- **Streak freeze**, Duolingo's best mechanic. Earned from loot boxes, it
  saves the streak on a missed day. A reward that protects something the
  user is afraid to lose.
- **Residents move out.** Damage left unrepaired for days makes a family
  leave; their house goes dark. They come back when it is fixed. A dark
  window hurts more than a number going down.
- **Before and after.** The building card keeps a picture of the building
  at its best, so a surrender's cost can be seen next to it.

### The goal gradient (people speed up near the finish)

- **Near-miss prompt.** When a countdown ends close to a finish line:
  "12 more minutes finishes Hart's Bakery. Extend?" The most direct way to
  turn a 50-minute session into a 62-minute one.
- **Endowed progress.** Every new building starts with its foundations
  laid, about 10% done. Progress already given makes finishing more likely.
- **Collection sets.** "Main Street: 4 of 5 shops." Completing a set unlocks
  something visible: the street's plaza, its lights, a market day.

### Commitment devices (pay to win, turned around)

- **Stake coins on a session.** "Bet 200 coins I finish 90 minutes."
  Finish: double back. Surrender: the stake is lost. The user pays now to
  make quitting cost more later, which is the core idea of the app.
- **Diamonds to expedite**, as planned in `docs/progression.md`, capped (at
  most 25% of a building). The building's memory keeps the real focused
  hours, so the city stays honest about the work.

### Seasons (a free battle pass)

- **A monthly season track**: focused hours advance it; rewards are seasonal
  blueprints (winter market, harvest fair, lantern festival). FOMO is
  strong, so seasonal items come back in later years; otherwise missing one
  becomes a reason to give up.
- **Daily and weekly quests that train deep work**: "a session before
  10 am", "one 90-minute session", "no surrender this week". These are
  where loot boxes come from.

### Attachment

- **Residents with names, who write.** A thank-you note when their home is
  finished; "the café is our favourite place". People get attached to
  characters they look after (the Tamagotchi effect).
- **Renaming** (already decided in `docs/progression.md`): people value
  what they made their own (the IKEA effect).

## Tactics that would backfire

- **Rewards for opening the app.** Login bonuses, "collect rent every
  4 hours" timers, pop-up chests. Idle games run on these, and they would
  make DeepWork a distraction. Rewards are collected when a session ends.
- **Rewards during a session.** No boxes, shop or quests while a session
  runs; only the construction site rising. If the app is interesting
  mid-session, it competes with the work.
- **Uncapped bonuses.** A stopwatch left running while the user scrolls on
  their phone still earns, and the daemon cannot tell. Stop the length bonus
  at about 3 h so leaving it running does not pay. `MAX_SESSION` stays.
- **Streaks with no way back.** Losing a long streak often makes people quit
  outright ("I've already ruined it"). Pair streaks with the freeze and a
  **rested bonus**: the first session after a break earns double coins, so
  the comeback feels good.
- **Long box-opening animations.** One satisfying reveal, skippable. More
  is just watching the app.

## Notes for the build

- Every random roll (shiny odds, box contents) is made by the daemon from
  the ledger with a fixed seed, so restarting the app or restoring a backup
  cannot reroll it, and the illusion stays fair.
- First progression v2 build, most effect for least work: shiny
  buildings, the near-miss prompt, the streak freeze, the rested bonus.
  Built 2026-11-06 (details in the checklist of `docs/progression.md`);
  the freeze is earned per 7 streak days until loot boxes exist.
- Later: seasons, quests, staking, residents' letters and move-outs,
  collection sets.
