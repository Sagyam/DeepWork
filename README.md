<img src="assets/icon.svg" width="64" height="64" alt="">

# DeepWork

A focus app for Linux that is hard to get around. During a focus session it
slows distracting sites down at the network layer (DNS-informed nftables sets +
tc/netem). Your browser keeps working for real work. Routines start sessions on
their own, and quitting early costs you progress in a small virtual world.

Status: phases 1–4 done (daemon, routines, hardening, the world, the app,
deeper enforcement, settings and backups, and an Arch package). See
[docs/PLAN.md](docs/PLAN.md).

## Layout

| Path | What |
|---|---|
| `crates/daemon` | `deepworkd`, the root daemon: sessions, DNS forwarder, nft/tc enforcement, SQLite ledger |
| `crates/cli` | `deepwork`, the CLI |
| `crates/agent` | `deepwork-agent`, desktop notifications and nudges |
| `crates/proto` | IPC types (newline-delimited JSON over a Unix socket) |
| `ui/` | `deepwork-ui`, the Tauri window: 3D city, timer and the full settings sheet |
| `dist/` | systemd unit, example config, install script |

## Develop without root

```sh
cargo test
cargo run -p deepworkd -- --dry-run          # logs nft/tc commands instead of running them
DEEPWORK_SOCKET=$XDG_RUNTIME_DIR/deepwork-dev.sock cargo run -p deepwork -- start 25m
cargo run -p deepworkd -- --print-rules      # show the exact nft ruleset and tc script
```

## Install

On Arch, as a package (`bun` is a makedepend, for the window):

```sh
cd dist
makepkg -si                 # installs to /usr, then:
sudo systemctl enable --now deepworkd.service
systemctl --user enable --now deepwork-agent.service
```

Every push to `main` builds the package in Actions; download the
`deepwork-git-x86_64` artifact from the latest `package` run and
`sudo pacman -U` the tarball inside it.

Or build and install straight from the source tree, into `/usr/local`:

```sh
./dist/install.sh            # builds, installs to /usr/local, enables deepworkd.service
deepwork start 50m           # countdown
deepwork start --stopwatch   # stopwatch, can be stopped after 10 minutes
deepwork status
deepwork surrender           # the only way out of a countdown; it takes 10 minutes
deepwork world               # the city your sessions built, and what giving in cost
deepwork config export backup.json   # settings + progress in one file
deepwork config import backup.json
./dist/install.sh uninstall
```

Created in [T3 Code](https://t3.codes).
