<img src="assets/icon.svg" width="64" height="64" alt="">

# DeepWork

A focus app for Linux that is hard to get around. During a focus session it
slows distracting sites down at the network layer (DNS-informed nftables sets +
tc/netem). Your browser keeps working for real work. Routines start sessions on
their own, and quitting early costs you progress in a small virtual world.

Status: phase 1 (core daemon + CLI). See [docs/PLAN.md](docs/PLAN.md).

## Layout

| Path | What |
|---|---|
| `crates/daemon` | `deepworkd`, the root daemon: sessions, DNS forwarder, nft/tc enforcement, SQLite ledger |
| `crates/cli` | `deepwork`, the CLI |
| `crates/proto` | IPC types (newline-delimited JSON over a Unix socket) |
| `dist/` | systemd unit, example config, install script |

## Develop without root

```sh
cargo test
cargo run -p deepworkd -- --dry-run          # logs nft/tc commands instead of running them
DEEPWORK_SOCKET=$XDG_RUNTIME_DIR/deepwork-dev.sock cargo run -p deepwork -- start 25m
cargo run -p deepworkd -- --print-rules      # show the exact nft ruleset and tc script
```

## Install

```sh
./dist/install.sh            # builds, installs to /usr/local, enables deepworkd.service
deepwork start 50m           # countdown
deepwork start --stopwatch   # stopwatch, can be stopped after 10 minutes
deepwork status
deepwork surrender           # the only way out of a countdown; it takes 10 minutes
./dist/install.sh uninstall
```

Created in [T3 Code](https://t3.codes).
