# DeepWork: Development

Implementation notes for contributors and agents. The design, threat model and
checklists live in [PLAN.md](PLAN.md), which is the source of truth.

## Layout

| Path | What |
|---|---|
| `crates/daemon` | `deepworkd`, the root daemon: sessions, DNS forwarder, nft/tc enforcement, SQLite ledger |
| `crates/cli` | `deepwork`, the CLI |
| `crates/agent` | `deepwork-agent`, desktop notifications and nudges |
| `crates/proto` | IPC types (newline-delimited JSON over a Unix socket) |
| `ui/` | `deepwork-ui`, the Tauri window: 3D city, timer and the full settings sheet |
| `dist/` | systemd units, example config, PKGBUILD, install scripts; `dist/packaging/` the deb / rpm / tarball packaging |
| `assets/` | README logo, screenshots and demo GIF |

## How it works

During a focus session the daemon slows distracting sites down at the network
layer: a DNS forwarder fills nftables sets with the addresses of listed
domains, tc/netem adds latency and caps bandwidth for them, and SNI inspection
catches connections the DNS path misses. The browser keeps working for real
work. Routines start sessions on their own, and quitting early costs progress
in the city. See PLAN.md for the threat model and every countermeasure.

## Develop without root

```sh
cargo test
cargo run -p deepworkd -- --dry-run          # logs nft/tc commands instead of running them
DEEPWORK_SOCKET=$XDG_RUNTIME_DIR/deepwork-dev.sock cargo run -p deepwork -- start 25m
cargo run -p deepworkd -- --print-rules      # show the exact nft ruleset and tc script
```

UI in a browser against the mock daemon:

```sh
cd ui
bun run dev        # then open http://localhost:5173/?mock=city
```

Scenarios: `empty`, `hamlet`, `city`, `metropolis`, `session`, `stopwatch`,
`surrender`, `ruins`; `&hour=16` fixes the time of day. In the console,
`city.demo("collapse" | "build" | "damage")` plays one transition.

## Install

From a release, on any supported distribution:

```sh
curl -fsSL https://raw.githubusercontent.com/Sagyam/DeepWork/main/dist/get.sh | sh
```

`dist/get.sh` reads `/etc/os-release`, downloads the matching asset from the
latest GitHub release, checks it against `SHA256SUMS`, installs it with apt,
dnf, zypper or pacman, and enables `deepworkd` and the user agent
(`DEEPWORK_VERSION=v0.2.0` pins a release, `DEEPWORK_NO_ENABLE=1` only
installs). By hand:

```sh
sudo apt install ./deepwork_0.1.0-1_amd64.deb      # Debian, Ubuntu
sudo dnf install ./deepwork-0.1.0-1.x86_64.rpm     # Fedora
sudo zypper install --allow-unsigned-rpm ./deepwork-0.1.0-1.x86_64.rpm   # openSUSE
sudo pacman -U ./deepwork-git-*.pkg.tar.zst        # Arch
tar xf deepwork-0.1.0-x86_64-linux.tar.gz && sudo ./deepwork-0.1.0-x86_64-linux/install.sh
sudo systemctl enable --now deepworkd.service
systemctl --user enable --now deepwork-agent.service
```

On Fedora the throttle needs `sch_netem` from `kernel-modules-extra` (a weak
dependency of the rpm); minimal Ubuntu kernels may need
`linux-modules-extra-$(uname -r)`.

On Arch, as a package built from source (`bun` is a makedepend, for the window):

```sh
cd dist
makepkg -si                 # installs to /usr, then:
sudo systemctl enable --now deepworkd.service
systemctl --user enable --now deepwork-agent.service
```

Or build and install straight from the source tree, into `/usr/local`:

```sh
./dist/install.sh            # builds, installs to /usr/local, enables deepworkd.service
./dist/install.sh uninstall
```

## Releases

`.github/workflows/release.yml` runs on `v*` tags (and by hand, for
artifacts only). It builds on Ubuntu 22.04 (glibc 2.35) for x86_64 and
aarch64, lays the tree out with `dist/packaging/stage.sh`, turns it into a .deb and
an .rpm with [nfpm](https://nfpm.goreleaser.com) (`dist/packaging/nfpm.yaml`, with
`postinstall.sh` / `preremove.sh` / `postremove.sh` mirroring the Arch install
scriptlet) and a tarball with `dist/packaging/tarball-install.sh`, installs the .deb
on the runner as a smoke test, calls `package.yml` for the Arch package, and
publishes everything with `SHA256SUMS` as a GitHub release.

```sh
# bump version in Cargo.toml (the workflow refuses a tag that doesn't match)
git tag v0.1.0 && git push origin v0.1.0
```

`package.yml` still builds the Arch package on every push to `main`
(artifact `deepwork-git-x86_64`). Nothing is signed or pushed to a package
repository yet: AUR, COPR, OBS or a PPA need accounts, and a signed apt / dnf
repository needs a key in the repo secrets.

## CLI

```sh
deepwork start 50m           # countdown
deepwork start --stopwatch   # stopwatch, can be stopped after 10 minutes
deepwork status
deepwork surrender           # the only way out of a countdown; it takes 10 minutes
deepwork world               # the city your sessions built, and what giving in cost
deepwork config export backup.json   # settings + progress in one file
deepwork config import backup.json
```

## README media

Screenshots and `assets/demo.webp` come from the mock UI in headless Chromium
(Playwright), 1280x800, `&hour=16`. Launch it on the real GPU
(`--use-angle=gl --ignore-gpu-blocklist`); SwiftShader manages ~3 fps.

The demo is a montage, captured frame by frame with `page.clock.install()` and
`clock.runFor(100)` between screenshots (10 fps, no dropped frames):

| Clip | Scenario | Action |
|---|---|---|
| Set a timer | `hamlet` | drag `.clockdial` from 30 to 50 min, click Start focus |
| Growth | `hamlet`, `city`, `metropolis` | 1.6 s each |
| Collapse | `surrender` | `city.demo("collapse")` |
| Settings | `metropolis` | cog, then Stats, then Site lists |

ffmpeg adds a caption per clip (`drawtext`, Noto Sans Bold 40 px), joins them
with 0.3 s `xfade`s, and encodes an animated WebP at 720 px, quality 55
(about 6 MB; the swaying trees make GIF 2-3x larger).
