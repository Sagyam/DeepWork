# Architecture

How DeepWork enforces focus, what it defends against, and the rails that
keep it from locking anyone out. For the game see [GAME.md](GAME.md), for
the window [APP.md](APP.md).

## Goals

1. Runs in the background as root. Not opt-in: it pushes you to start.
2. Countdown and stopwatch sessions; routines start sessions on a schedule.
3. Enforces at the DNS and packet level, never by killing processes. The
   browser keeps working for real work.
4. Throttles (slow pages, buffering video) rather than blocks, by default.
5. Hard to bypass for a Linux user with sudo, once a session runs.
6. Every early quit or detected bypass costs progress in the city.

## Safety rails (never remove)

- `MAX_SESSION` (6 h) is a hard cap in code (`session.rs`).
- **Surrender** always works: type a long phrase, wait 10 minutes with
  enforcement on, the session ends with a heavy penalty.
- The PAM gate **fails open**: missing gate, crash, 2 s timeout or daemon
  down all allow.
- **TTY root login** is never blocked. It is the emergency exit:

  ```sh
  # Ctrl+Alt+F3, log in as root
  rm /run/systemd/system/deepworkd.service.d/50-session.conf
  systemctl daemon-reload; systemctl stop deepworkd
  nft destroy table inet deepwork
  rm /run/systemd/resolved.conf.d/zz-deepwork.conf; systemctl restart systemd-resolved
  python3 -I dist/pam.py remove    # optional: unhook PAM entirely
  ```

## Components

```
user session (untrusted)            root                        kernel
┌──────────────────────┐   unix    ┌────────────────────────┐   ┌──────────────────────┐
│ deepwork (CLI)       │  socket   │ deepworkd              │   │ nft table inet       │
│ deepwork-agent       │ ────────▶ │  session engine        │──▶│   deepwork           │
│  (notify, bar)       │  JSON +   │  scheduler (routines)  │   │ tc prio + netem      │
│ deepwork-ui (Tauri)  │  peercred │  DNS forwarder         │   │  egress + IFB ingress│
└──────────────────────┘           │  enforcer (nft, tc)    │   │ NFQUEUE (SNI)        │
                                   │  tamper watch          │   └──────────────────────┘
                                   │  store (SQLite)        │
                                   └────────────────────────┘
```

**All policy and state live in `deepworkd`.** Clients are untrusted views:
they can ask to start a session, never end one outside the rules.

| Crate | Binary | Role |
|---|---|---|
| `crates/proto` | | IPC types (newline-delimited JSON) |
| `crates/daemon` | `deepworkd` | Root daemon |
| `crates/cli` | `deepwork` | CLI, also `deepwork bar` |
| `crates/agent` | `deepwork-agent` | User unit: notifications, heads-ups, nudges |
| `ui/` | `deepwork-ui` | Tauri window ([APP.md](APP.md)) |

| Choice | Detail |
|---|---|
| Language | Rust everywhere; tokio; hickory-proto for DNS parsing |
| nft / tc | Driven through their CLIs (`nft -f -`, `tc -batch -`): atomic, inspectable. Rendering is pure (`enforcer/nft.rs`, `enforcer/tc.rs`); only `enforcer/mod.rs` runs commands |
| Store | SQLite in `/var/lib/deepwork`, root-owned. The ledger of sessions and events is the source of every derived number |
| Config | TOML in `/etc/deepwork/config.toml`; the config *in effect* lives in the store |
| IPC | `/run/deepwork/deepworkd.sock` (0666), caller identified by `SO_PEERCRED` |
| Platform | Linux with systemd only. Snap / Flatpak can't host a root daemon with PAM hooks |
| Bar | The user runs the Omarchy shell, not Waybar; `deepwork bar` serves both |

## Sessions and routines

- **Countdown**: cannot be stopped, only surrendered. `Extend` adds time,
  never past `MAX_SESSION`.
- **Stopwatch**: stoppable after `stopwatch_min` (10 min); ends at `MAX_SESSION`.
- Elapsed time accrues from monotonic ticks and is persisted, so suspend,
  reboot and clock changes cannot shorten a session.
- **Routines** (`[[routines]]`): name, days, start, length, profile. A run
  is `(routine, local date)`, recorded once (started or skipped). It starts
  late if the machine slept or another session ran, for what is left of its
  window. `skip_tokens_per_week` (default 2) limits skips.
- **Nudges**: inside `[nudge]` hours with no session for `after_mins`, a
  level that rises every `repeat_mins`; the agent shows it.

## Network enforcement

1. **DNS forwarder** (`dns.rs`, `127.0.0.1:5454`, plain or DoT upstreams,
   one pipelined connection each in `dot.rs`). During a session a runtime
   drop-in points systemd-resolved at it. This is what keeps the user's
   strict DoT (NextDNS) working while port 853 is blocked. Outside sessions
   DNS is untouched, so a daemon crash cannot break it.
2. Answers for rule domains fill nft sets `slow_v4/v6` or `block_v4/v6`
   (timeout TTL + slack). Session start restarts resolved and pre-resolves
   every rule domain.
3. **nft table `inet deepwork`**: block sets get reset / drop; slow sets get
   the throttle mark; all port 53 not from the daemon is redirected to it;
   port 853, known DoH IPs and UDP 443 (QUIC) are dropped. Same rules in the
   forward hook for containers and VMs; their DNS is DNAT'd to
   `dns.container_dns`.
4. **tc** on every real interface: `prio` + `fq_codel`, throttle-marked
   packets to a `netem` band; ingress through an IFB (`dwifb<ifindex>`).
   Default throttle (profile `deep`): +400 ms, 50 ms jitter, 256 kbit/s, no
   loss. Tuned on real use: 240p video buffers, pages crawl; stricter felt
   like a block.
5. **SNI inspection** (`sni.rs`, `nfqueue.rs`; `inspect_sni`, on): new TLS
   connections are queued until the ClientHello is read. A rule match slows
   or resets; any other name passes at full speed even on a slowed address
   (shared CDNs); no name keeps the address verdict. Queue uses `bypass`, so
   it fails open.
6. **Escalation**: every 15 s, throttled traffic over 16 KiB adds 15 s of
   "distracted" time; profile `escalation` stages tighten the throttle.
7. **Browser policies** (`enforcer/browser.rs`): Firefox and Chromium
   families get DoH and ECH locked off, re-applied at startup, session start
   and every minute.

## Threat model

| Bypass attempt | Countermeasure |
|---|---|
| Close the app | The UI is only a view |
| Kill / stop the daemon | Rules stay (fail closed); `Restart=always`; `RefuseManualStop=yes` during sessions |
| Reboot, suspend, change the clock | Session persisted; time on monotonic ticks; wall-clock jumps > 2 min logged `clock_jump` |
| Short manual session to dodge a routine | The routine waits and runs after it |
| `dig @8.8.8.8`, DoT, DoH, QUIC | Redirected; 853, DoH IPs and UDP 443 dropped; browser DoH locked off |
| `sudo nft flush ruleset`, edit one rule or qdisc | `nft monitor`, `tc monitor`, `ip monitor link` trigger a fingerprint check; repaired within a second, logged `tamper` |
| `sudo`, `su`, `pkexec`, `run0`, cached polkit | PAM gate and polkit rule ask the daemon; refused during sessions (`escalation_denied`) |
| Loosen the config | Waits 24 h (`LOOSEN_DELAY`); tightening is instant |
| `docker run --privileged` | Optional `lock_docker` (off: the user doesn't need it): socket closed to the group during sessions. VMs are ignored |
| Shared CDN IP, hardcoded IP, stale cache | SNI inspection judges by name |
| SSH SOCKS / userspace proxy (Tor, v2ray, ...) | Detected (`tunnel.rs`), minor penalty every 10 min; not blocked |
| Kernel VPN, Tailscale exit node | Not a bypass: nft sees packets before encryption |
| Live USB, GRUB cmdline, TTY root | Out of scope; TTY root is the intended exit |

Details worth knowing before changing these:

- **Config** (`cfgstate.rs`, `loosen.rs`): on start, reload or the app's
  Save, the daemon compares the file with the config in effect. Stricter or
  neutral applies now; looser waits 24 h (an edit restarts the wait,
  reverting cancels it); a broken file is ignored. Stricter profiles apply
  to a running session at once. `[dns]` changes apply on restart.
- **Root lock**: `dist/pam.py` puts a `pam_exec` gate at the top of `sudo`,
  `sudo-i`, `su`, `su-l` and `polkit-1` (`auth` and `account`, so cached
  credentials are covered). It is built so that any gate failure skips
  `pam_deny`. Root callers are always allowed.
- **Tamper repair** keeps the dynamic sets' contents and timeouts across a
  re-apply; a device whose shaping fails is retried after 30 s, not in a loop.
- **Docker lock** saves the socket mode to `/var/lib/deepwork/docker-sock.mode`
  and restores it at session end or the next start. Rootless sockets are
  left alone.
- **Tunnels**: listening sockets from `/proc/net/tcp*` mapped to processes;
  flags `ssh -D`, known proxy clients and ports 1080 / 9050 / 9150. A
  renamed proxy is not caught; the aim is that the easy ways cost something.

## Inverted mode

Off by default (`[inverted]`). Outside sessions the enforcer runs in
`Mode::Ambient` with the inverted profile: same throttle, but no root lock,
stop lock, Docker lock, escalation or penalties (repairs are logged
`ambient_repair`). Completed sessions earn free minutes (`free.rs`) that
`deepwork free` spends to lift the throttle.

## Known gaps

- HTTP/2 connection coalescing could carry a rule site over a passed
  connection whose certificate covers it (same IP). Not seen yet.
- Ubuntu 22.04's polkit 0.105 ignores JS rules; only PAM guards polkit there.
- Not covered: NixOS (declarative PAM), non-systemd distributions, snap
  Chromium's policy path.
