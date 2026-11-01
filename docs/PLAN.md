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
| `docker run --privileged` (user is in `docker` group) | Accepted risk for now (user does not expect to go that far). Optional `docker.sock` lock later | 4 |
| Tailscale exit node | nft output hook sees packets before WireGuard; still matched | 1 |
| Browser's own DoH (Zen had strict mode 3) | Locked managed policy turns DoH off; browser DoH endpoint IPs blocked | 1 |
| Shared CDN IPs (YouTube vs Google Docs) | SNI inspection of new TLS connections via NFQUEUE | 4 |
| SSH SOCKS tunnel / personal VPN | Heuristic detection + penalty only | 4 |
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
   they are covered too. During a session, forwarded port 53 to any other
   server (Docker's `1.1.1.1` fallback, `--dns`) is DNAT'd to
   `dns.container_dns` (`172.17.0.1:53` here) or refused if that is unset.

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

Keep assets minimal (procedural shapes) until the rules feel right.

## Decisions taken (revisit if needed)

| Question | Default |
|---|---|
| Docker during sessions | Not locked. The user doesn't need Docker now and won't go that far to bypass. Optional lock moved to phase 4 |
| VMs (libvirt) | Not used; ignore |
| Throttle vs block | Throttle by default ("painfully slow"), block per domain |
| Theme | City skyline prototype; may change. World model stays theme-agnostic |
| UI order | CLI + bar module first, Tauri UI in phase 3 |
| Bar | The user's bar is the Omarchy shell (quickshell), not Waybar. `deepwork bar` serves both |

## Next session: start here

Phase 2 code is complete (2026-11-02). Routines, the agent and the bar are
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

Then phase 3 (the world).

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
