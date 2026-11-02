# DeepWork: Plan

A focus app for Linux that is hard to get around. It slows down distracting sites
at the network layer during focus sessions, starts sessions on a schedule, and
ties every early quit or bypass to a loss in a small virtual world.

This file is the source of truth across work sessions. Update the checklists as
things land.

## Requirements

1. Runs in the background as root. Not opt-in: it pushes you to start.
2. Countdown and stopwatch sessions.
3. Routines: focus slots that start on their own.
4. Enforcement at the DNS / packet level, never by killing processes. The
   browser must keep working for study and work.
5. Throttling (buffering, slow images) is preferred over hard blocking.
6. Hard for a Linux-savvy user with sudo to bypass once a session is running.
7. A virtual progression system where breaking focus costs you something.

## Threat model

The user has the sudo password, so a determined bypass is always possible. The
design goal is:

- A bypass takes more effort than the urge lasts.
- Every bypass we can detect costs progress in the game, so even a successful
  bypass is not free.
- A bug must never lock the user out of their own machine.

| Bypass attempt | Countermeasure | Phase |
|---|---|---|
| Close the app | UI is only a view; the daemon enforces | 1 |
| Kill the daemon | nft table and tc qdiscs stay in place (fail closed); `Restart=always` | 1 |
| Reboot | Active session persisted in SQLite and re-applied at boot | 1 |
| Suspend through a countdown | Elapsed time accrues on `CLOCK_MONOTONIC`, which excludes suspend | 1 |
| Change the wall clock | Elapsed time never uses wall clock | 1 |
| Change the wall clock to dodge a routine | Routines follow the wall clock, so drift against `CLOCK_BOOTTIME` > 2 min is logged as `clock_jump` | 2 |
| Start a short manual session right before a routine | The routine waits and starts when that session ends, for what is left of its window | 2 |
| Hardcoded DNS server (`dig @8.8.8.8`) | nft redirects all port 53 to our resolver; port 853 dropped | 1 |
| DNS-over-HTTPS in the browser | Known DoH IPs dropped; `use-application-dns.net` canary; managed browser policies | 1 / 2 |
| HTTP/3 (QUIC) | UDP 443 dropped during sessions, browsers fall back to TCP | 1 |
| `sudo nft flush ruleset` | Periodic re-assert + tamper event; `nft monitor` repairs within a second; PAM sudo lock | 1 / 2 |
| Delete or insert one nft rule, edit one tc qdisc / filter | Fingerprints (`nft -t list table` + DoH sets, `tc ... show` per device) taken after applying; any difference is re-applied and logged | 2 |
| `systemctl stop deepworkd` | `RefuseManualStop=yes` during sessions, polkit rule | 2 |
| `sudo` anything | PAM hook denies sudo / su / polkit auth during sessions, also with cached credentials | 2 |
| `pkexec`, `run0`, cached polkit approval | polkit rule asks the daemon for systemd1, resolve1 and pkexec actions | 2 |
| Edit config to loosen | The config in effect lives in the store; loosening edits wait 24h (`deepwork config`), tightening is immediate; a broken file is ignored | 2 |
| `docker run --privileged` (user is in `docker` group) | Optional per profile (`lock_docker`): group access taken off `/run/docker.sock` during sessions; reopening it is a tamper event. Off by default | 4 (done) |
| Tailscale exit node | nft output hook sees packets before WireGuard; still matched | 1 |
| Browser's own DoH (Zen had strict mode 3) | Locked managed policy turns DoH off; browser DoH endpoint IPs blocked | 1 |
| Shared CDN IPs (YouTube vs Google Docs) | SNI inspection of new TLS connections via NFQUEUE | 4 (done) |
| Hardcoded IP / stale DNS cache for a rule site | SNI inspection judges the connection by name, whatever the address | 4 (done) |
| Inverted mode: `sudo nft destroy table` outside a session | Put back within a second and logged (`ambient_repair`), no penalty: root is not locked then, and package upgrades reload firewalls. Stopping the daemon lifts nothing (the table stays until reboot) | 4 (done) |
| SSH SOCKS tunnel / userspace proxy (Tor, v2ray, ...) | Detected while running (listening proxy process), minor penalty every 10 min; not blocked | 4 (done) |
| Personal VPN (WireGuard, OpenVPN) | Not a bypass: nft sees packets before the tun device encrypts them, tc shapes new devices | n/a |
| Live USB, GRUB cmdline, TTY root login | Out of scope. TTY root is the intended emergency exit | n/a |

### Config changes (phase 2)

- The config in effect is stored in SQLite (`kv` table). On start,
  `deepwork config reload` or SIGHUP (`systemctl reload deepworkd`), the
  daemon compares `/etc/deepwork/config.toml` with it:
  - same, or only stricter / neutral: applied now;
  - looser (`loosen.rs`: removed rules or profiles, block -> throttle, gentler
    throttle, QUIC allowed, fewer / shorter / moved routines, more skip
    tokens, shorter stopwatch minimum or surrender wait, weaker nudges, a
    different default profile): stored as pending and applied 24h later;
  - edited again while pending: the 24h restarts; put back: cancelled;
  - unparseable: ignored while a config is in effect (only a broken file on
    the very first start is fatal).
- `[dns]` changes are neutral and take effect on the next daemon start.
- The delay (`LOOSEN_DELAY`) is in code, not config. `config_applied` and
  `config_pending` events go to the ledger.

### Root lock (phase 2)

- `deepwork-pam-gate` (in `/usr/local/lib/deepwork/`) asks the daemon
  (`Request::Gate`) and exits 0 only to deny. `dist/pam.py` puts this block at
  the top of `sudo`, `sudo-i`, `su`, `su-l` and `polkit-1`:

  ```
  auth     [success=ignore default=1] pam_exec.so quiet quiet_log stdout <gate>
  auth     requisite pam_deny.so
  account  (same two lines)
  ```

  Any failure of the gate (missing, crash, 2s timeout, daemon down) skips
  `pam_deny`, so it fails open by construction. `account` also runs when sudo
  has cached credentials. Root callers are always allowed.
- `/etc/polkit-1/rules.d/10-deepwork.rules` asks the same gate for
  `org.freedesktop.systemd1.*`, `org.freedesktop.resolve1.*` and pkexec, which
  catches cached polkit approvals. Fails open the same way.
- Every refusal is an `escalation_denied` event in the ledger.
- During a session `/run/systemd/system/deepworkd.service.d/50-session.conf`
  sets `RefuseManualStop=yes`; it is removed when the session ends.
- Verified without root: a C harness with `pam_start_confdir` runs the real
  block: allows with no daemon, a missing gate, a hung daemon (fails open
  after 2s per stage) and no session; denies with the message during a session.
- **Emergency exit** (TTY root, `Ctrl+Alt+F3`): `rm /run/systemd/system/deepworkd.service.d/50-session.conf;
  systemctl daemon-reload; systemctl stop deepworkd; nft destroy table inet deepwork;
  rm /run/systemd/resolved.conf.d/zz-deepwork.conf; systemctl restart systemd-resolved`.
  Or `python3 -I dist/pam.py remove` to unhook PAM entirely.

### Safety rails (never remove)

- Hard maximum session length (`MAX_SESSION`, 6h) baked into the code.
- **Surrender**: type a long phrase, wait 10 minutes with enforcement still on,
  then the session ends with a heavy game penalty.
- TTY root login is never blocked.
- The PAM sudo lock asks the daemon; if the daemon is unreachable, it allows.

## Architecture

```
user session (untrusted)            root                        kernel
┌──────────────────────┐   unix    ┌────────────────────────┐   ┌──────────────────────┐
│ deepwork (CLI)       │  socket   │ deepworkd              │   │ nft table inet       │
│ deepwork-agent       │ ────────▶ │  session engine        │──▶│   deepwork           │
│  (notify, waybar)    │  JSON +   │  scheduler (routines)  │   │  sets, marks, DNS    │
│ deepwork-ui (Tauri)  │  peercred │  DNS resolver          │   │  redirect            │
└──────────────────────┘           │  enforcer (nft, tc)    │   │ tc prio + netem      │
                                   │  tamper watch          │   │  egress + IFB ingress│
                                   │  store (SQLite)        │   └──────────────────────┘
                                   └────────────────────────┘
```

All policy and all state live in `deepworkd`. Clients are untrusted views: a
client can ask to start a session, but cannot end one early except through the
rules (stopwatch minimum, surrender).

### Workspace layout

| Crate | Binary | Role |
|---|---|---|
| `crates/proto` | | IPC types shared by everything |
| `crates/daemon` | `deepworkd` | Root daemon |
| `crates/cli` | `deepwork` | CLI client |
| `crates/agent` | `deepwork-agent` | User service: notifications, heads-ups, escalating nudges |
| `ui/` | `deepwork-ui` | Tauri 2 + three.js window: 3D city and session HUD |

### Tech choices

- **Rust** for everything. Single static binaries, safe parsing of network input,
  shared types with Tauri.
- **tokio** runtime, **hickory-proto** for DNS message parsing.
- **nft / tc via their CLIs** (`nft -f -`, `tc -batch -`), not netlink bindings.
  nft scripts are atomic transactions and the exact rules are easy to inspect.
- **SQLite** (`rusqlite`, bundled) in `/var/lib/deepwork`, root-owned.
- **TOML** config in `/etc/deepwork/config.toml`, root-owned.
- IPC: newline-delimited JSON over `/run/deepwork/deepworkd.sock` (mode 0666),
  caller identified with `SO_PEERCRED`.

### Network enforcement

1. `deepworkd` runs a DNS forwarder (default `127.0.0.1:5454` and `[::1]:5454`)
   with plain or DNS-over-TLS upstreams. During a session only, a runtime
   drop-in (`/run/systemd/resolved.conf.d/zz-deepwork.conf`) points
   systemd-resolved at it. This is required because resolved on this machine
   uses strict DoT to NextDNS, and port 853 is blocked during sessions. Outside
   sessions DNS is untouched, so a daemon crash cannot break it.
2. When a session is active and a resolved name matches a profile rule, every
   A/AAAA address in the answer goes into `slow_v4/v6` or `block_v4/v6` with a
   timeout of TTL + slack.
3. At session start: restart resolved (empties its cache) and pre-resolve all
   rule domains (4 at a time) to seed the sets.
4. nft table `inet deepwork` (only present during a session):
   - `block_*`: TCP reset / drop.
   - `slow_*`: `ct mark` + `meta mark` set to the throttle mark.
   - All port 53 traffic not to resolved's stub (`127.0.0.53`) and not carrying
     the daemon's exempt socket mark is redirected to our resolver. Port 853
     dropped. Known DoH resolver IPs dropped on 443.
   - UDP 443 dropped.
   - Same rules in the forward hook so containers and VMs are covered.
5. tc on every real interface (re-scanned each tick):
   - Egress: `prio` root with all traffic in band 1 (`fq_codel`); the `fw`
     filter sends throttle-marked packets to band 2 (`netem` delay, jitter,
     rate, loss).
   - Ingress: `clsact` + `connmark` action restores the mark, `mirred` redirects
     to an IFB device (`dwifb<ifindex>`) with the same prio/netem setup.
6. The daemon's own upstream DNS sockets use `SO_MARK` with the exempt mark.
7. Docker containers resolve through resolved's extra stub (`172.17.0.1`), so
   they are covered too. During a session, forwarded port 53 to any other
   server (Docker's `1.1.1.1` fallback, `--dns`) is DNAT'd to
   `dns.container_dns` (`172.17.0.1:53` here) or refused if that is unset.

SNI inspection (phase 4, profile `inspect_sni`, on by default): chains
`sni_output` / `sni_forward` (priority filter - 1) queue packets of
established TCP connections to port 443 whose conntrack mark is still unjudged
(0 or the address throttle) to NFQUEUE 17495 with `bypass`. The daemon
(`nfqueue.rs`, raw netlink, no crate; `sni.rs`, pure) reads the ClientHello,
reassembling it over segments (Chrome's post-quantum hello takes two) and
records, and answers with the judgement as the packet mark; `enforce` copies
it into the conntrack mark so the connection is never queued again:

- rule match → `0x445b` slow (tc has a second `fw` filter for it on the IFB)
  or `0x445a` block (`ct direction original` reset; without the direction
  check the RST it sends was rejected too and the connection hung);
- a name no rule matches → `0x4459` pass, full speed even on an address in
  `slow_*` (the shared CDN case);
- no name, an encrypted ClientHello (ECH outer name only), mid-stream data of a
  connection opened before the session, or nothing after 3 empty packets →
  "keep": slow if the address sets say so, pass otherwise.

Fail-open by design: if nobody reads the queue (daemon killed, module
missing), `bypass` lets packets through unjudged and the address sets apply as
before. Known gap: HTTP/2 connection coalescing could carry a rule site over a
passed connection whose certificate also covers it (same IP required); not
seen yet, watch for it on Google properties.
Verified in `unshare -rnm` with the real daemon, a veth to a second namespace
and `openssl s_server` (100 KB, default throttle): YouTube SNI on an unknown
address 4.3 s; Docs 0.2 s; Reddit reset at once; with the server address in
`slow_v4/v6` Docs 0.4 s and YouTube 4.7 s over v4 and v6; no SNI 4.7 s; after
`kill -9` of the daemon the address sets still throttle; no false tamper.

Tunnel heuristics (phase 4, `tunnel.rs`): kernel VPNs are covered by the
rules above, but a userspace proxy encrypts inside a process, so DNS, the
sets and SNI never see what goes through it. Every reassert (15s) during a
session the daemon reads `/proc/net/tcp{,6}` for listening sockets and maps
them to processes through `/proc/<pid>/fd`. Flagged: `ssh` with dynamic
forwarding (`-D`, `-o DynamicForward`, combined flags; plain `-L` / `-R`
are work and ignored), known proxy clients (tor, shadowsocks, v2ray / xray,
sing-box, clash / mihomo, hysteria, trojan, gost, chisel, naive, brook,
microsocks, sshuttle, wstunnel, psiphon, lantern; by `comm` or argv[0/1]),
and anything listening on 1080 / 9050 / 9150. Each is a `tunnel` event
(minor penalty in the world, agent notifies) when first seen and again every
10 min while it runs. A renamed proxy on another port is not caught; the goal
is only that the easy ways cost something. Verified with a dry-run daemon:
a fake `ssh -N -D 1080` is logged within 15s and the world shows the damage;
`ssh -L` is not. Nothing listening on the host matches today (cloudflared is
deliberately not on the list).

Tamper watch (phase 2): `nft monitor ruleset`, `tc monitor` and
`ip monitor link` run for the life of the daemon. A matching line queues one
check (bursts coalesce); the check compares fingerprints and repairs. When the
table is re-applied, addresses in the dynamic sets are saved from
`nft -j list set` and restored with their remaining timeouts; if they are lost
(table deleted) the rule domains are primed again. A device whose shaping
fails is retried after 30s, so a failure cannot loop through `tc monitor`.
Re-shaping clears `clsact` first (a leftover ingress filter made
`filter replace` fail, so a partly removed setup was never repaired before).
Verified in `unshare -rnm` with the real daemon: rule delete, accept insert,
`nft flush ruleset`, root / clsact / fw filter / netem / IFB edits are all
repaired within a second; a new dummy interface is shaped within a second.

Verified in a throwaway user + network namespace (`unshare -rn`, veth pair,
HTTP server): a 400 KB download goes from 2 ms to 14.5 s once the server IP is
in `slow_v4`, and fails outright in `block_v4`.

Throttle defaults (profile "deep"): +400ms RTT, 50ms jitter, 256 kbit/s, no
loss, 1 second netem queue.

Escalation (phase 2): every reassert (15s) the daemon reads the netem byte
counters of all shaped devices and IFBs (`tc -s -j qdisc show`); a window
with at least 16 KiB of throttled traffic adds 15s of "distracted" time.
Profiles list `escalation` stages (`after_mins`, `throttle`); defaults:
after 10 min 192 kbit/s +500ms, after 20 min 128 kbit/s +600ms (not tuned on
real sites yet). A stage change runs `tc qdisc change` on every device
(connections kept) and refreshes the tamper fingerprints. Distracted time is
in memory and restarts with the daemon. Status shows `distracted_secs` and
`escalation_stage`; the agent notifies "Throttle tightened". Verified in
`unshare -rnm`: stage 1 after 60s of traffic, no false tamper. The goal is a **subtle nudge, not a ban**: pages
still load, just slowly, and 240p video buffers now and then.

Real-world data points (YouTube "stats for nerds", user's machine):

| Setting | Result |
|---|---|
| 128 kbit/s, +800ms, 2% loss, 2s queue | Felt like a full block. Loss + delay hold TCP to ~126 kbit/s (`MSS / RTT * 1.22 / sqrt(loss)`) |
| 512 kbit/s, +300ms, no loss, 1s queue | ~400 kbit/s, 480p plays comfortably. Too lenient |
| 256 kbit/s, +400ms, no loss, 1s queue | **Confirmed default.** 240p plays with buffering; images on X take ~30 s. "Perfect" |

### Docker socket lock

Being in the `docker` group is root in all but name (`docker run --privileged
-v /:/host` flushes the nft table without sudo, so the PAM lock does not
help). With `lock_docker = true` in the session's profile, `enforcer/docker.rs`:

- at session start saves the socket's mode to `/var/lib/deepwork/docker-sock.mode`
  and removes group and other access from `/run/docker.sock` (`0660` -> `0600`);
- on every re-assert (15s) closes it again if it is open (a Docker restart
  makes a new socket), logged as `tamper` if it had been closed this session;
- at session end, and at startup outside a session (after a crash), restores
  the saved mode and removes the file. With no saved mode it leaves the
  socket alone, so a socket closed on purpose stays closed.

Running containers keep running. Missing socket (Docker not installed or
not started): nothing to do. Rootless Docker / Podman sockets belong to the
user and grant no root, so they are not touched.

### Inverted mode

Off by default (`[inverted] enabled = true` turns it on at once; turning it
off, a higher earn rate, a bigger bank or another profile wait 24h).

- Outside sessions the enforcer runs in `Mode::Ambient` with the inverted
  profile (`default_profile` if unset): the same nft / tc / resolver setup
  as a session, but no stop lock, no Docker lock, no PAM refusal and no
  escalation or tunnel scan. A session switches the enforcer to
  `Mode::Session` in place (one nft transaction, tc re-applied per device)
  and back again when it ends, without lifting everything in between.
- Completed sessions (not surrendered) earn `free_mins_per_hour` per focused
  hour into a bank capped at `max_bank_mins` (`free.rs`, stored in `kv` as
  `free_bank`; ledger events `free_earned`, `free_start`, `free_end`).
- `deepwork free [duration]` (or the app's button) lifts the throttle until
  the bank or the span runs out; `deepwork free --stop` banks the rest.
  Spending needs at least a minute banked and no session; starting a session
  stops it. Time is counted from monotonic ticks, so suspend does not use it.
- Changes to the ambient rules are put back like in sessions but logged as
  `ambient_repair` without penalty. The point is friction, not a lock.
- If applying fails, the daemon releases everything and retries every 60s.

### Session model

- `Countdown { duration }`: stopping early is not possible; only surrender.
- `Stopwatch`: can be stopped after `stopwatch_min` (10 min). Auto-completes at
  `MAX_SESSION`.
- Elapsed time accrues from `Instant` deltas on each tick and is persisted, so
  suspend, reboots and clock changes cannot shorten a session.
- States: `Active`, `Surrendering { until }`, `Completed`, `Surrendered`.

### Routines, skips and nudges

- `[[routines]]` in the config: name, days, local start time, duration,
  optional profile. Each run is identified by `(routine, local date)` and
  recorded once in `routine_runs` (`started` or `skipped`), so a surrendered
  routine never restarts and a skip cannot be reused.
- A run is due while `start <= now < end`. If the machine was asleep, the
  daemon was down or another session was running, it starts late with what is
  left of the window (at least 1 minute). A failed start retries after 60s.
- Skip tokens: `skip_tokens_per_week` (default 2, Monday to Sunday). A skip
  applies to the next run of a routine within 24h that has not started.
- Nudges: inside `[nudge]` active hours with no session for `after_mins`, the
  daemon reports a level that rises every `repeat_mins`; quiet when a routine
  starts within `after_mins`. The agent always shows the first nudge gently
  (low, then normal, then critical) and replaces the previous one.
- Clients: `deepwork routines`, `deepwork skip [routine]`, and `deepwork bar`
  (one line of Waybar-style JSON; works as an Omarchy shell `command` module,
  see `dist/bar-module.md`). `deepwork-agent` polls status every 2s and
  sends notifications with `notify-send`; it runs as a user unit under
  `graphical-session.target`.

## Progression (phase 3, polished last)

The theme may change, so the game is split in two:

1. **A theme-agnostic world model in the daemon**, derived from the ledger. It
   knows about plots, a growth stage per plot, damage, streaks and currency
   (focused minutes). The UI can never edit progress.
2. **A theme renderer in the UI** that turns the model into pictures. Swapping
   themes means writing a new renderer, not touching the rules.

Prototype theme: **City skyline. A tiny settlement grows into a metropolis.**
It was picked because it's the easiest of the three to draw procedurally:
buildings are rectangles with window grids, and density, height, lit windows and
a day/night sky make growth visible without hand-made assets. The other
candidates were a jungle growing from bare land (needs organic shapes, and is
close to Forest) and a mansion built from one empty room (needs many distinct
furniture assets).

Rules, mapped onto the skyline:

- Each session works on a building under construction (scaffolding, crane).
  Completing it finishes the building; longer sessions build taller or rarer
  buildings.
- Quit early: the building under construction collapses into rubble.
- Surrender: a blackout or fire spreads to nearby buildings. They stay damaged
  until the next completed session repairs them.
- Detected tamper: an earthquake damages a whole district.
- The settlement grows in tiers (hamlet → town → city → metropolis) as the
  total of focused hours grows. Streaks speed up repairs.

Assets are generated, not hand-made: buildings and trees come from a Blender
script (see "The app"), so they can be tuned like code.

### World model (phase 3, built)

`world.rs` folds the ledger into a `World` (proto type) on every
`Request::World`; nothing is stored, so it cannot drift from the ledger and
clients cannot edit it. Inputs: ended sessions (completed / surrendered, with
focused time) and `tamper`, `escalation_denied`, `clock_jump` events, sorted by
time. Theme-agnostic terms: plots (index, district of 8, grade 0-4, damage
0-2, rubble, seed), a construction site for the running session, tier 0-3,
streak, and a history of the last 30 changes with their cause.

| Ledger | World |
|---|---|
| Completed session | Builds on the oldest rubble, else a new plot. Grade from length: 25 / 50 / 90 / 180 min. Time counts toward the tier. Then repairs `1 + mins / 25` damage levels, most damaged first; doubled on a 3+ day streak |
| Surrendered session (severe) | Its plot becomes rubble, fire does 2 damage to the 3 nearest buildings, its time does not count, the streak resets |
| `tamper` (major) | Earthquake: 1 damage to every building in the biggest district |
| `escalation_denied`, `clock_jump`, `tunnel` (minor) | 1 damage to the newest building |

- Damage 3 turns a building into rubble; the grade it had is lost for good.
- Bursts count once: a second quake (or a second minor penalty) within 10 min is ignored.
- Tiers at 10 / 50 / 200 focused hours. Streak: consecutive local days with a
  completed session, kept until the end of the next day.
- Numbers are first guesses, like the escalation stages; tune on real use.
- Clients: `deepwork world` (text skyline, `--json`), and `deepwork-agent`
  notifies losses (collapse, earthquake, damage) within ~10s. Builds are left
  to the "Session complete" note.

### The app (phase 3, built)

`ui/`: Tauri 2 shell (`ui/src-tauri`, crate `deepwork-ui`, outside the
workspace's default members so `cargo test` stays light) and a Vite +
TypeScript + three.js frontend, built with bun.

- The shell has one command, `daemon`, which forwards a `Request` to the
  socket (`DEEPWORK_SOCKET` or the default) and returns the `Response`
  (`Gate` refused). No state, no policy: the daemon decides, as for the CLI.
- The frontend polls `Status` every second and `World` every 5s (and at once
  when the session changes). `ui/src/proto.ts` mirrors `crates/proto` by hand.
- City theme in 3D (three.js, with a kit generated in Blender). The 2D Pixi
  skyline was the first try; the user found it flat ("nothing to be proud
  of, nothing to lose"), so it was replaced on the same day.
  - `city/plan.ts` (pure, unit tested with `bun test`): the `World` as a city
    plan. A district is a block of 8 lots (4 x 2) ringed by road; blocks go
    in a square spiral from the centre, so the city grows outward. Grade
    picks the kind and size: cottage (gable roof, chimney, hedge, garden
    tree), shop (lit shop window, awning, neon sign), apartment block
    (balconies, water tank), office tower (glass, setback, antenna),
    landmark (three tiers, gold trim and crown, spire, beacon). Empty lots
    of a block are staked out with tape; countryside trees grow with the tier.
  - Kit (`ui/blender/city_kit.py`, run with `bun run kit`; made with
    Blender 5.2): writes `ui/public/city-kit.glb` (74 pieces, ~3.4 MB). Modular
    pieces per kind: ground storey, floor storeys, roof. Styles: four
    cottages (gable, hip, front gable with porch, bay window under a gambrel
    with dormers); shops (two shopfronts with awnings, a café with arched
    fanlights, an oriel and umbrella tables); apartments (balconies, Juliet
    balconies, brick walk-up with fire escapes); offices (curtain wall, fins,
    brutalist punched concrete; setback, plant room or helipad); landmarks
    in two styles picked per building: art deco (stone piers, gold ledges
    and finials, a lit stepped crown with sunburst chevrons and spire) and
    modern glass (fins, sky-garden ledges, LED bands, tapered glass crown).
    Also six trees (incl. birch and pink cherry), a lattice tower crane
    (mast sections, jib sections, cab, counter-jib with weights, trolley,
    hook, steel load), four cars and a bus, and a pedestrian. Bevelled trim, recessed windows with sills, cornices with brackets,
    quoins, striped awnings and glowing shop lettering, balconies, water
    tanks, roof gardens, curtain walls, a helipad. Ambient occlusion is baked
    per corner into vertex colours (BVH ray casts, ground plane for ground
    pieces). Materials are named by role (`wall`, `trim`, `window`, ...);
    window panes map to one cell each of a 32 x 32 atlas. Anchors (chimney
    smoke, beacons) are glTF extras. Generated `.glb` is committed; rerun the
    script after editing it. `--preview out.png` renders Cycles views.
  - `city/kit.ts` loads the kit before the scene starts (`City.create`).
    `city/models.ts` stacks pieces to the plan's floor count, scaled in x / z
    to the lot (offices step in to 78% above 68% of their floors), and picks
    materials per role from the building's palette and damage. The window
    atlas (`city/textures.ts`) is drawn on canvases: glass, curtains and blinds
    by day, warm lit rooms at night, smashed and burning windows when broken;
    cells shift per storey so lit windows differ. Damage 1 darkens and smokes;
    damage 2 stacks only the lower ~3/4 with no roof, smashed windows, rubble
    chunks and rebar on top, fire and heavy smoke.
    Rubble is a heap of concrete, wall and burnt chunks with bent beams,
    bigger for a bigger building. The site: concrete floors up to its
    progress, the finished lower storeys from the kit, columns, scaffolding a
    floor above the work, the kit crane (mast stacked to height, jib length
    from the lot, pendant ties, hook and load), a translucent
    blueprint of the finished building (red while surrendering, when the
    site also trembles), and a tower crane that swings.
  - `city/scene.ts`: Sky shader with the sun by local time, stars and
    moonlight at night, shadows, ACES tone mapping, bloom on lit windows,
    lamps and beacons, fog. Orbit camera (drag / zoom), slow auto-rotate after
    30s idle, framed to the city's size.
  - Countryside: `city/terrain.ts` (pure, unit tested) is the land itself —
    low swells out of town, wooded foothills and a ring of peaks, a river in
    a floodplain with a lake, and a road graded over the hills to the truss
    bridge. `city/land.ts` builds it: one flat-shaded facet per triangle,
    coloured by height, slope, forest cover and water's edge, with forests
    instanced from the kit (real trees up close, canopy clumps further out)
    plus scrub and boulders, so the city sits in jungle rather than on a lawn.
  - Street life (`city/traffic.ts`): cars, vans, taxis and buses (tier 2+)
    loop each block in the right-hand lane, evenly spaced at one speed per
    loop so they never collide; pedestrians walk the pavement both ways.
    Counts grow with the tier (cars 1-4, people 2-11 per block). One
    InstancedMesh per model part; head / tail lights and signs light at
    night. The loop path (`blockLoop` in `plan.ts`) is unit tested.
  - Transitions are animated: collapse (the building shakes, tilts and sinks
    into a dust cloud while debris rains down; rubble appears as it clears),
    completion (the building rises out of dust, gold sparks at the top),
    damage (jolt and dust), repair (sparks). The camera turns to the plot.
  - Replay: the last seen history time is kept in `localStorage`; on opening,
    unseen events play one by one from a reconstructed earlier state, with a
    line of narration ("You surrendered. Plot 5 collapsed ..."), so a loss
    is watched, not just counted.
  - Performance on the host's Radeon 610M: 60 fps (vsync) in the app for the
    real hamlet; the 120-plot metropolis at night ~100 fps uncapped in
    GPU Chromium with the old box models, ~90 with the Blender kit and traffic
    (hamlet ~170). `VITE_FPS=1 bun run build` adds a frame-rate readout.
- HUD: tier and progress, building condition; session card (timer, building
  progress, throttled time and stage, stop when allowed, surrender with the
  phrase typed by hand: paste and drop are refused); idle card (nudge, next
  routine, skip, start 25 / 50 / 90 min, custom, stopwatch, profile); the
  last five world events.
- Routines and Stats panels (tabs under the city card, Esc closes). Routines:
  the configured routines (`Request::Routines`), the next 24 hours of runs
  with a Skip per routine's next run, tokens left. Skips are confirmed in a
  dialog, as the CLI insists on a terminal. Stats (`Request::History`, ended
  sessions since a time, newest first, at most 2000; folded in the pure
  `stats.ts`, unit tested): today / this week / 28 days focused, completed,
  surrendered, streak; focused time per local day for 14 days (bars with a
  tooltip, a red dot under days with a surrender); the last 10 sessions.
  Panels refetch with the world (5s). A loosening config change waiting
  behind its delay (`ConfigStatus`) shows as a card with its reasons.
- A renderer failure only loses the picture: the HUD keeps working and the
  error shows in a banner.
- Dev: `cd ui && bun run dev`, then `http://localhost:5173/?mock=city` in a
  browser (`empty`, `hamlet`, `city`, `metropolis`, `session`, `stopwatch`,
  `surrender`, `ruins`; `&hour=21` fixes the time of day). The mock daemon
  answers whenever the page is not inside Tauri; `city.demo("collapse")` in
  the console plays a transition.
- Verified on the host (2026-11-02) against the installed daemon: the real
  hamlet (5 houses), nudge and history render in the window. Mock scenarios
  and the collapse / completion animations checked in headless Chromium.

## Decisions taken (revisit if needed)

| Question | Default |
|---|---|
| Docker during sessions | Not locked by default. The user doesn't need Docker now and won't go that far to bypass. `lock_docker = true` in a profile closes the socket |
| VMs (libvirt) | Not used; ignore |
| Throttle vs block | Throttle by default ("painfully slow"), block per domain |
| Theme | City, in 3D (three.js, kit generated by a Blender script). World model stays theme-agnostic |
| UI order | CLI + bar module first, Tauri UI in phase 3 |
| Bar | The user's bar is the Omarchy shell (quickshell), not Waybar. `deepwork bar` serves both |

## Next session: start here

Phase 3 (2026-11-02): world model, penalties and the Tauri app with the
3D city are in (see "World model" and "The app" above), and so are the
Routines and Stats panels (2026-11-02, checked with the mock and against a
dry-run daemon; the installed daemon needs `./dist/install.sh` to answer the
new `history` / `routines` requests). Phase 3 code is complete. Still to do on real
use: tune the city (sizes, damage looks, replay pacing); ideas: sound for
collapse / completion, weather.

Phase 4 (2026-11-02): SNI inspection is in (see "Network enforcement"),
tested in namespaces only. Host check after `./dist/install.sh`: start a
session, `journalctl -u deepworkd` shows "SNI inspection reading queue";
`RUST_LOG=deepworkd=debug` shows `sni <name>: Slow / Pass`; YouTube still
throttled, Google Docs / Gmail now at full speed. Tunnel / proxy heuristics are in too
(see "Network enforcement"); after reinstalling, `ssh -N -D 1080 <host>`
during a session should show `tunnel` in `journalctl -u deepworkd` and damage
in `deepwork world`. The docker.sock lock is in (profile `lock_docker`, off
by default; see "Docker socket lock"), tested on a real socket in a temp dir
and in dry-run. Host check: set `lock_docker = true` (tightening, so it
applies at once), start a session: `ls -l /run/docker.sock` shows
`srw-------`, `docker ps` says permission denied; after the session it is
`srw-rw----` again. Inverted mode is in too (see "Inverted mode"), checked
end to end with a dry-run daemon. Host check: `[inverted] enabled = true`,
`deepwork config reload`: YouTube is slow with no session, `sudo` still works;
complete a short session, `deepwork status` shows the earned minutes,
`deepwork free` makes YouTube fast, `deepwork free --stop` slows it again.
Next in phase 4: packaging (PKGBUILD).

Phase 2 code is complete. Routines, the agent and the bar are
confirmed on the host; the rest (root lock, tamper watch, browser policies in
the daemon, DoT reuse, container DNS, config delay, escalation) is tested in
namespaces / dry-run only. Host check after `./dist/install.sh`, keeping a
root shell (`sudo -s`) open in another terminal while testing PAM:

1. Outside a session: `sudo true` works; `deepwork config` says no change.
2. Start `deepwork start 5m --profile trial`:
   - `sudo true` and `pkexec true` are refused with the DeepWork message;
     `systemctl stop deepworkd` is refused; TTY root still works.
   - `sudo nft delete rule ...` is impossible now, so tamper repair is only
     testable from the root shell: delete a rule, `nft list table inet
     deepwork` shows it back within a second; `journalctl -u deepworkd`
     shows `tamper`.
   - YouTube still throttled, DNS still fine (DoT reuse), Zen policy file
     has `network.dns.echconfig.enabled` locked off.
3. After the session: sudo works again; `systemctl stop` works again.
4. Later: tune escalation stages and nudges on real use; then add real
   `[[routines]]`.
5. After reinstalling: `deepwork world` shows the city built from past
   sessions; `deepwork-agent` (restart the user unit) notifies losses;
   `deepwork-ui` (installed when bun is present, with a desktop entry) shows
   the 3D city and a running session's construction site.

## Phases

### Phase 1: Core daemon (done)

- [x] Cargo workspace, `proto` crate, IPC protocol
- [x] Config (TOML) with built-in default profile
- [x] Session engine (countdown, stopwatch, surrender, max cap) with unit tests
- [x] SQLite store: sessions, event ledger, active-session recovery
- [x] nft ruleset + tc script rendering (pure, unit tested)
- [x] Enforcer: system mode (runs nft/tc) and dry-run mode (logs scripts)
- [x] DNS forwarder: UDP + TCP, rule matching, set insertion, canary domain
- [x] Unix socket server + CLI (`start`, `status`, `stop`, `surrender`)
- [x] Periodic re-assert of the nft table, tamper event when missing
- [x] DNS-over-TLS upstreams; session-only resolved drop-in
- [x] systemd unit, example config, install script (`dist/`)
- [x] Managed browser policies turning DoH off (first `dist/browser-policies.py`, now in the daemon). The user's Zen had strict DoH (`network.trr.mode = 3`), which bypassed the resolver entirely
- [x] First real run (2026-11-01): 5 min `trial` profile. Zen and Chromium were
      both throttled, the session completed on its own, teardown restored DoT
      to NextDNS. Feedback: too harsh, felt like a block, so defaults retuned
- [x] systemd `Type=notify` readiness (install.sh raced the socket before)
- [x] Commit the first version, public repo github.com/Sagyam/DeepWork

### Phase 2: Routines and hardening

- [x] Routines in config + scheduler with 5 minute heads-up
- [x] Skip tokens
- [x] `deepwork-agent`: notifications, escalating nudges; `deepwork bar` module (Waybar / Omarchy shell)
- [x] Wall-clock jump detection (`clock_jump` event), since routines use the wall clock
- [x] First real routine run on the host (2026-11-02): 10 min `smoke-test` routine
      throttling only example.com started on its own, heads-up and bar worked, ended
      on time and lifted the throttle
- [x] PAM sudo lock (`pam_exec` querying the daemon, fail open). Covers sudo, su, su-l and polkit-1 (pkexec, run0, systemctl password prompts)
- [x] polkit rule; `RefuseManualStop=yes` (runtime drop-in, only during sessions)
- [x] `nft monitor` based tamper detection (plus `tc monitor`; fingerprints catch partial edits)
- [x] Config changes through the daemon only; 24h delay for loosening (`cfgstate.rs`, `loosen.rs`)
- [x] Re-apply browser policies at session start (Zen package updates overwrite `policies.json`); ECH off for phase 4.
      Now in the daemon (`enforcer/browser.rs`, `deepworkd --browser-policies apply|remove`), synced at
      startup, session start and every minute, plus a pacman hook. Firefox family: locked `DNSOverHTTPS`
      and `network.dns.echconfig.enabled` / `http3_echconfig.enabled` off; Chromium family:
      `DnsOverHttpsMode=off`, `EncryptedClientHelloEnabled=false`
- [x] Link watch instead of periodic interface scan (`ip monitor link`, kept to CLIs like the rest)
- [x] DoT connection reuse: one pipelined connection per upstream (`dot.rs`), internal message IDs,
      20s idle close, one retry on a stale connection. Live: first query ~170 ms, then ~6 ms
- [x] Truncate UDP answers larger than the client's EDNS size (TC set, question only)
- [x] Redirect forwarded port 53 from containers / VMs: prerouting DNAT to `dns.container_dns`
      (IPv4, from docker* / br-* / virbr*), otherwise refused in the forward hook; forwarded IPv6
      DNS always refused. Tested with a bridge + veth "container" namespace
- [x] Throttle escalation over time spent on a site (per-profile `escalation` stages, on by default)

### Phase 3: The world

- [x] Ledger → theme-agnostic world model in the daemon (`world.rs`, `Request::World`, `deepwork world`)
- [x] Tauri 2 app with a 3D city (three.js) renderer (`ui/`), animated losses and builds
- [x] Building and tree kit generated in Blender (`ui/blender/city_kit.py`): modular storeys, baked AO, window atlas
- [x] More styles (second landmark style, café, brick walk-up, brutalist office, gambrel cottage), lattice crane, traffic and pedestrians
- [x] Timer, routines and stats screens: timer, start / stop / surrender in the session card; Routines and Stats panels;
      `Request::History` / `Request::Routines` (also `deepwork history`, `deepwork routines`); pending config notice
- [x] Penalty tiers wired to surrender / tamper / refused root / clock jump events (surrender is the only early quit); agent notifies losses

### Phase 4: Deeper enforcement

- [x] NFQUEUE SNI inspection for new TLS connections (`sni.rs`, `nfqueue.rs`; profile `inspect_sni`)
- [x] Tunnel / VPN heuristics (`tunnel.rs`: listening proxy processes during a session → `tunnel` penalty; kernel VPNs need nothing)
- [x] Optional docker.sock lock during sessions (`enforcer/docker.rs`, profile `lock_docker`, off by default)
- [x] Inverted mode: distractions throttled always, free minutes earned by focus (`[inverted]`, `free.rs`,
      `enforcer::Mode::Ambient`, `deepwork free`; agent, bar and app show the bank)
- [ ] Packaging (PKGBUILD)
