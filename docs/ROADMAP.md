# Roadmap

What is left to do. Only open work lives here: when an item lands, delete
it (git history keeps the record) and update the doc that describes the
area, if anything a reader needs changed.

## Status

| Area | State |
|---|---|
| Daemon, enforcement, hardening ([ARCHITECTURE.md](ARCHITECTURE.md)) | Done. Several parts tested only in namespaces / dry-run (see host checks) |
| Game, progression v2 ([GAME.md](GAME.md)) | Built; untuned |
| App and realistic city ([APP.md](APP.md)) | Built; models for every current blueprint and public building |
| Packaging | Arch, deb, rpm, tarball; `get.sh`; first release `v2026.11.0` |

## Next, in order

1. **Use it for real** and tune: coin prices, build hours, shiny odds,
   escalation stages, nudges. Add real `[[routines]]`.
2. **Models**: O2 or O3 (the default order builds six identical O1 towers
   at 50-98 h), then a second workshop (timber mill or brewery; S4 is the
   only one, so the mayor never chooses).
3. **The master plan's real layout** in `ui/src/city/plan.ts`: streets,
   districts, reserved ground for squares and landmarks; a test that its
   lot ids match `plan.rs`. Then L5 city hall grows to its half block, and
   L6 town square and L12 city park replace the squares and parks
   assembled from props.
4. **Before-and-after picture** on the deed card.

## Host checks

Tested in namespaces or dry-run only. Run on the host after a reinstall,
with a root shell open in another terminal for the PAM checks.

- [ ] Root lock: during `deepwork start 5m --profile trial`, `sudo true`,
      `pkexec true` and `systemctl stop deepworkd` are refused; TTY root
      works; after the session all work again.
- [ ] Tamper: from the root shell, delete an nft rule; it is back within a
      second and `journalctl -u deepworkd` shows `tamper`.
- [ ] SNI: journal shows "SNI inspection reading queue"; YouTube slow,
      Google Docs and Gmail at full speed.
- [ ] Tunnel: `ssh -N -D 1080 <host>` during a session logs `tunnel` and
      damages the city.
- [ ] Docker lock: with `lock_docker = true`, `/run/docker.sock` is
      `srw-------` during a session and `srw-rw----` after.
- [ ] Inverted mode: YouTube slow with no session, `sudo` works;
      `deepwork free` lifts it, `--stop` restores it.
- [ ] Settings and backup in the app: add a blocked domain (applies now),
      remove one (24 h notice), export and re-import (0 new sessions).
- [ ] Progression: `deepwork world` shows the existing city rebuilt on the
      plan; `deepwork build <need>` takes over.
- [ ] Model pack: `deepwork-ui` from the next release shows the download
      line, then the realistic city.
- [ ] Install on a real Debian / Ubuntu and Fedora machine and repeat.

## Rendering

- [ ] Measure in the real Tauri window (WebKitGTK is usually slower than
      Chromium) with `VITE_FPS=1`. Target: 30 fps end-game city on a
      610M-class iGPU.
- [ ] Hamlet trees cost ~3.5 ms of its ~21 ms GPU: cut-out leaves at MSAA.
- [ ] Instancing: one InstancedMesh per piece and material instead of
      merged `Parts`.
- [ ] Shrink the pack further: the AO bakes are ~90 MB of it, one channel
      stored as BC7; BC4 (RGTC) would halve them.
- [ ] Retune lighting: it is still tuned for the flat kit.

## Packaging

- [ ] Publish the gzipped pack: `bun run pack --upload`, commit `models.json`.
- [ ] Signed packages and repositories (AUR, COPR / OBS, an apt repo); the
      user is creating the accounts.

## Ideas, not designed

Check each against the rule in [GAME.md](GAME.md#the-one-rule).

- **Metropolis and beyond**: open-ended needs in expansion districts once
  the plan runs out.
- **Diamonds and loot boxes**: a rare currency that repairs or speeds up a
  build (capped, and memories keep the real focused hours). Boxes only from
  daily streak goals, never bought; seeded by the daemon so nobody can
  reroll; a pity counter; rarity tiers (diamonds, blueprint variants,
  decorations, unique landmarks). Freezes move there.
- **Seasons and quests**: a monthly track advanced by focused hours;
  quests that train deep work ("one 90-minute session"). Seasonal items
  return in later years so missing one isn't a reason to quit.
- **Staking**: bet coins on finishing a session; double back or lose it.
- **Endowed progress**: new sites start ~10% built.
- **Collection sets**: "Main Street: 4 of 5 shops" unlocks a plaza or lights.
- **Residents**: thank-you letters; families move out of long-unrepaired
  homes and come back when fixed.
- **Repairs as gameplay**: repair needs that cost build hours or diamonds.
- **Sound** for completion, collapse and level-up; **weather**.
