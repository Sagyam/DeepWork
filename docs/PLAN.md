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
| Hardcoded DNS server (`dig @8.8.8.8`) | nft redirects all port 53 to our resolver; port 853 dropped | 1 |
| DNS-over-HTTPS in the browser | Known DoH IPs dropped; `use-application-dns.net` canary; managed browser policies | 1 / 2 |
| HTTP/3 (QUIC) | UDP 443 dropped during sessions, browsers fall back to TCP | 1 |
| `sudo nft flush ruleset` | Periodic re-assert + tamper event; later `nft monitor` and a PAM sudo lock | 1 / 2 |
| `systemctl stop deepworkd` | `RefuseManualStop=yes`, polkit rule | 2 |
| `sudo` anything | PAM hook in `/etc/pam.d/sudo` denies sudo during sessions | 2 |
| Edit config to loosen | Loosening changes wait 24h; tightening is immediate | 2 |
| `docker run --privileged` (user is in `docker` group) | Accepted risk for now (user does not expect to go that far). Optional `docker.sock` lock later | 4 |
| Tailscale exit node | nft output hook sees packets before WireGuard; still matched | 1 |
| Browser's own DoH (Zen had strict mode 3) | Locked managed policy turns DoH off; browser DoH endpoint IPs blocked | 1 |
| Shared CDN IPs (YouTube vs Google Docs) | SNI inspection of new TLS connections via NFQUEUE | 4 |
| SSH SOCKS tunnel / personal VPN | Heuristic detection + penalty only | 4 |
| Live USB, GRUB cmdline, TTY root login | Out of scope. TTY root is the intended emergency exit | n/a |

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
| `crates/agent` | `deepwork-agent` | User service: notifications, nudges, Waybar JSON (phase 2) |
| `ui/` | `deepwork-ui` | Tauri 2 + PixiJS (phase 3) |

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
   they are covered too. Containers with a hardcoded `--dns` on the default
   bridge are a known gap (forwarded port 53 is not redirected yet).

Verified in a throwaway user + network namespace (`unshare -rn`, veth pair,
HTTP server): a 400 KB download goes from 2 ms to 14.5 s once the server IP is
in `slow_v4`, and fails outright in `block_v4`.

Throttle defaults (profile "deep"): +400ms RTT, 50ms jitter, 256 kbit/s, no
loss, 1 second netem queue. The goal is a **subtle nudge, not a ban**: pages
still load, just slowly, and 240p video buffers now and then.

Real-world data points (YouTube "stats for nerds", user's machine):

| Setting | Result |
|---|---|
| 128 kbit/s, +800ms, 2% loss, 2s queue | Felt like a full block. Loss + delay hold TCP to ~126 kbit/s (`MSS / RTT * 1.22 / sqrt(loss)`) |
| 512 kbit/s, +300ms, no loss, 1s queue | ~400 kbit/s, 480p plays comfortably. Too lenient |
| 256 kbit/s, +400ms, no loss, 1s queue | Current default, not yet tried |

### Session model

- `Countdown { duration }`: stopping early is not possible; only surrender.
- `Stopwatch`: can be stopped after `stopwatch_min` (10 min). Auto-completes at
  `MAX_SESSION`.
- Elapsed time accrues from `Instant` deltas on each tick and is persisted, so
  suspend, reboots and clock changes cannot shorten a session.
- States: `Active`, `Surrendering { until }`, `Completed`, `Surrendered`.

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

Keep assets minimal (procedural shapes) until the rules feel right.

## Decisions taken (revisit if needed)

| Question | Default |
|---|---|
| Docker during sessions | Not locked. The user doesn't need Docker now and won't go that far to bypass. Optional lock moved to phase 4 |
| VMs (libvirt) | Not used; ignore |
| Throttle vs block | Throttle by default ("painfully slow"), block per domain |
| Theme | City skyline prototype; may change. World model stays theme-agnostic |
| UI order | CLI + Waybar first, Tauri UI in phase 3 |

## Next session: start here

1. Ask the user to re-run `./dist/install.sh` (needs their sudo password). That
   installs the 256 kbit/s throttle. They try `deepwork start 5m --profile
   trial` and report whether 240p video buffers now and then while pages still
   load. Tune `Throttle::default` from the table above.
2. Then phase 2, starting with routines + the user agent (notifications,
   Waybar), then the PAM sudo lock and `RefuseManualStop`.

## Phases

### Phase 1: Core daemon (in progress)

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
- [x] Managed browser policies turning DoH off (`dist/browser-policies.py`). The user's Zen had strict DoH (`network.trr.mode = 3`), which bypassed the resolver entirely
- [x] First real run (2026-11-01): 5 min `trial` profile. Zen and Chromium were
      both throttled, the session completed on its own, teardown restored DoT
      to NextDNS. Feedback: too harsh, felt like a block, so defaults retuned
- [x] systemd `Type=notify` readiness (install.sh raced the socket before)
- [x] Commit the first version, public repo github.com/Sagyam/DeepWork

### Phase 2: Routines and hardening

- [ ] Routines in config + scheduler with 5 minute heads-up
- [ ] Skip tokens
- [ ] `deepwork-agent`: notifications, escalating nudges, Waybar module
- [ ] PAM sudo lock (`pam_exec` querying the daemon, fail open)
- [ ] polkit rule; `RefuseManualStop=yes`
- [ ] `nft monitor` based tamper detection
- [ ] Config changes through the daemon only; 24h delay for loosening
- [ ] Re-apply browser policies at session start (Zen package updates overwrite `policies.json`); ECH off for phase 4
- [ ] netlink link watch instead of periodic interface scan
- [ ] DoT connection reuse (one TLS handshake per query today)
- [ ] Truncate UDP answers larger than the client's EDNS size
- [ ] Redirect forwarded port 53 from containers / VMs
- [ ] Throttle escalation over time spent on a site

### Phase 3: The world

- [ ] Ledger → theme-agnostic world model in the daemon
- [ ] Tauri 2 app with a procedural PixiJS skyline renderer
- [ ] Timer, routines and stats screens
- [ ] Penalty tiers wired to quit / surrender / tamper events

### Phase 4: Deeper enforcement

- [ ] NFQUEUE SNI inspection for new TLS connections
- [ ] Tunnel / VPN heuristics
- [ ] Optional docker.sock lock during sessions
- [ ] Inverted mode: distractions throttled always, free minutes earned by focus
- [ ] Packaging (PKGBUILD)
