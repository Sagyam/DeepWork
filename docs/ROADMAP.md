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
2. **Models**: O2 or O3, then L2 (offices and towers are each one design,
   so ~200 of the plan's ~350 h build O1 or L1 over and over), then a
   second workshop (timber mill or brewery; S4 is the only one, so the
   mayor never chooses) and a third downtown shop (only S1 and S2 fit).
3. **Landmark ground**: reserve half blocks in `layout.rs` for L5 city
   hall and the landmarks; then L6 town square and L12 city park replace
   the parks assembled from props.
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
- [ ] Names: a new building gets a name from its pile, and its sign shows it.
- [ ] Model pack: `deepwork-ui` from the next release shows the download
      line, then the realistic city.
- [ ] Install on a real Debian / Ubuntu and Fedora machine and repeat.

## Rendering

- [ ] Measure in the real Tauri window (WebKitGTK is usually slower than
      Chromium) with `VITE_FPS=1`. Target: 30 fps end-game city on a
      610M-class iGPU.
- [ ] Trees: the leaf pre-pass took ~1.3 ms off the Hamlet's trees. Next,
      the far woods: a lumpy opaque canopy mesh, or octahedral impostors
      (the crossed cards show from the city's downward view and look like
      flat copper sheets under a low sun).
- [ ] Instancing: one InstancedMesh per piece and material instead of
      merged `Parts`.
- [ ] Shrink the pack further: the AO bakes are ~90 MB of it, one channel
      stored as BC7; BC4 (RGTC) would halve them.

## Packaging

- [ ] Signed packages and repositories (AUR, COPR / OBS, an apt repo); the
      user is creating the accounts.

## Ideas, not designed

Check each against the rule in [GAME.md](GAME.md#the-one-rule).

### Streets

- **Neighbourhood names** ("Millbrook", "the Canal Quarter") per block
  group, as labels when zoomed out; street signs at corners.
- **Junctions and structures**: signals only where busy streets meet,
  stop signs on lanes, a roundabout at district centres, a flyover where
  the highway meets downtown, an underpass under the river road.
- **Traffic with trips**: cars now roam the lane graph (`roads.ts`) at
  random. Next they leave a lot, route to another (homes to offices in the
  morning, shops at midday, home at dusk), park and vanish. Buses on fixed
  lines; volume follows what is built. Budget the CPU on the iGPU.
- **Congestion**, after trips: residents complain about jammed streets,
  and only a paid upgrade (a signal, a roundabout, widening) meets it.

### Coins and rewards

- **Land beyond the plan** (hills, the waterfront, across the river) for
  the open-ended Metropolis; buying a parcel picks its zoning.
- **Tune the economy**: land and road prices, `WEALTH_PCT`, goal targets
  and box odds are first guesses.
- **Seasons and quests**: a monthly track advanced by focused hours;
  quests that train deep work. Seasonal items return in later years.
- **Collection sets**: "Main Street: 4 of 5 shops" unlocks a plaza or
  lights. A finished street is a natural set.
- **Residents**: named families in the houses; thank-you letters naming
  their street; families leave long-unrepaired homes and come back.
- **On hold**: endowed progress (sites starting part built); it breaks
  "a 25 h tower means 25 h".
