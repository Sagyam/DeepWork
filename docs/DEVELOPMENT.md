# Development

Commands for building, running and releasing. How things work is in
[ARCHITECTURE.md](ARCHITECTURE.md) and [APP.md](APP.md).

## Layout

| Path | What |
|---|---|
| `crates/daemon` | `deepworkd`: sessions, DNS, nft/tc, SQLite ledger, the game (`plan.rs`, `world.rs`) |
| `crates/cli` | `deepwork` |
| `crates/agent` | `deepwork-agent` |
| `crates/proto` | IPC types |
| `ui/` | `deepwork-ui`: `src/` frontend, `src-tauri/` shell, `blender/` models, `scripts/` tooling |
| `dist/` | Units, example config, PKGBUILD, `install.sh`, `get.sh`; `packaging/` for deb / rpm / tarball |
| `assets/` | README media |

## Daemon, without root

```sh
cargo test
cargo clippy --all-targets
cargo run -p deepworkd -- --dry-run        # logs nft/tc commands instead of running them
cargo run -p deepworkd -- --print-rules    # the exact nft ruleset and tc script
DEEPWORK_SOCKET=$XDG_RUNTIME_DIR/deepwork-dev.sock cargo run -p deepwork -- start 25m
unshare -rn sh -c 'nft -f ruleset.nft'     # check a ruleset against a real kernel, host untouched
```

## UI

```sh
cd ui
bun test
bun run dev            # http://localhost:5173/?mock=city
bunx tauri build --no-bundle   # binary in target/release/deepwork-ui
```

**Mock scenarios** (`?mock=`): `empty`, `hamlet`, `city`, `metropolis`,
`session`, `stopwatch`, `surrender`, `ruins`, `desk`, `nearmiss`,
`levelup`, `inverted`. `&hour=16` fixes the time of day. In the console,
`city.demo("collapse" | "build" | "damage" | "graduate")` plays a transition.

### Models

```sh
bun run kit                  # low-poly kit -> public/city-kit.glb (committed)
bun run models               # every realistic model -> public/models/ (git-ignored, minutes)
bun run models c1 --no-tex   # one model, skip the shared texture library
bun run textures             # redo BC7 compression only (needs basisu)
```

Needs Blender and `basis-universal`. The dev server serves `public/models/`;
release builds leave it out. To run a release build on local models:
`DEEPWORK_MODELS=$PWD/ui/public/models target/release/deepwork-ui`.

| Page | Use | Main params |
|---|---|---|
| `/proto.html?model=c1` | One model on its lot | `floors`, `seed`, `damage=0..3`, `view=hero\|city\|detail\|roof\|back\|street`, `hour`, `count=N` (stress) |
| `/proto.html?props=cars` | A props model's pieces | `only=suv,hatch`, `gap`, `ry`, `view` |
| `/town.html` | Every model in a hand-laid town, with a perf panel | `view=overview\|downtown\|...`, `opt=0..8`, `aa=msaa\|smaa\|fxaa\|none`, `shadowmap`, `scale`, `still`, `fps=30` |

All pages take `cam=x,y,z&at=x,y,z&fov=`. A new model appears in the town
once added to `BLOCKS` in `ui/src/proto/town.ts`.

### Benchmarks

Headless system Chromium on this machine's GPU, with `bun run dev` running:

```sh
bun scripts/bench-town.ts "view=overview&opt=0" "view=overview"
HIDE=woods bun scripts/bench-town.ts "view=overview"     # what the woods cost
bun scripts/bench-app.ts "mock=metropolis" "mock=city&hour=22&cam=220,120,260,0,10,0"
# LUMA=1 prints mean brightness, SHOTS=dir saves screenshots
```

## Install

From a release: `curl -fsSL https://deepwork.sagyamthapa.com.np/get.sh | sh`
(`DEEPWORK_VERSION=v2026.11.0` pins, `DEEPWORK_NO_ENABLE=1` only installs).
The URL is a Vercel rewrite in `Sagyam/deepwork-site` to `dist/get.sh` on
`main`, so script changes go live on push.

```sh
sudo apt install ./deepwork_<ver>-1_amd64.deb             # Debian, Ubuntu
sudo dnf install ./deepwork-<ver>-1.x86_64.rpm            # Fedora (throttle needs kernel-modules-extra)
sudo zypper install --allow-unsigned-rpm ./deepwork-<ver>-1.x86_64.rpm
sudo pacman -U ./deepwork-git-*.pkg.tar.zst               # Arch
cd dist && makepkg -si                                    # Arch, from source
./dist/install.sh            # from the tree into /usr/local; `uninstall` removes
sudo systemctl enable --now deepworkd.service
systemctl --user enable --now deepwork-agent.service
```

**Never install or apply nft/tc/resolved changes on the host without the
user's go-ahead.**

## Releases

- CI (`ci.yml`): fmt, clippy `-D warnings`, `cargo test` on Rust changes;
  `tsc` and `bun test` on UI changes. Markdown triggers nothing.
- `package.yml` builds the Arch package on pushes to `main`.
- `release.yml` on a `v*` tag builds deb / rpm / tarball (x86_64, aarch64,
  Ubuntu 22.04 glibc) with nfpm, the Arch package, and publishes a GitHub
  release with `SHA256SUMS`. Notes come from merged PR labels.
- Versions are CalVer `YYYY.M.N` (month without leading zero, `N` from 0
  within the month).

```sh
# bump version in Cargo.toml, cargo update -w, commit; the workflow checks they match
git tag v2026.11.1 && git push origin v2026.11.1
```

### Model packs

After changing models:

```sh
cd ui
bun run models               # or just the changed ones
bun run pack --upload        # writes src-tauri/models.json, publishes models-<id>
# commit src-tauri/models.json; the next app build downloads the new pack
```

Old `models-*` releases can be deleted once no app release points at them.

## CLI

```sh
deepwork start 50m | --stopwatch      deepwork status
deepwork stop  (stopwatch only)       deepwork surrender
deepwork extend 10m                   deepwork world
deepwork routines | skip [routine]    deepwork free [duration] | --stop
deepwork buy [id]                     deepwork build <need> [--design id]
deepwork pause | rename <lot> "Name"  deepwork history
deepwork config reload | export f | import f
```

### Status bar

`deepwork bar` prints one line of Waybar JSON (`text`, `tooltip`, `class`:
`active`, `surrendering`, `upcoming`, `free`, `nudge`, `idle`, `down`).

```jsonc
// Omarchy shell, ~/.config/omarchy/shell.json, under bar.layout.<section>
{ "id": "deepwork", "type": "command", "exec": "deepwork bar", "interval": 1, "tooltip": "DeepWork" }
// Waybar
"custom/deepwork": { "exec": "deepwork bar", "return-type": "json", "interval": 1 }
```

## README media

Screenshots and `assets/demo.webp` come from the mock UI in headless
Chromium (Playwright, 1280x800, `&hour=16`, real GPU:
`--use-angle=gl --ignore-gpu-blocklist`). The demo is captured frame by
frame with `page.clock` (10 fps), captioned and joined with ffmpeg, and
encoded as animated WebP at 720 px. The social preview and the site's
`og.jpg` come from `og/card.html` in the site repo.
