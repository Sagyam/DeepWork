# DeepWork

Focus/time-blocking app for Linux (Omarchy/Arch, Hyprland). A root daemon throttles
distracting sites at the network layer during sessions. Multi-session project:
**`docs/PLAN.md` is the source of truth**. Read it first, and tick its checklists
when work lands.
`docs/DESIGN.md` is the design language shared with the landing site and
the user's other apps; UI changes follow it, in light and dark.
`docs/DEVELOPMENT.md` holds the layout, dev and install commands; keep
`README.md` a short visual pitch for passersby (media in `assets/`).

## Commands

- `cargo test`, `cargo clippy --all-targets`, `cargo fmt`
- `cargo run -p deepworkd -- --dry-run`: run the daemon unprivileged; commands are logged, not run
- `cargo run -p deepworkd -- --print-rules`: dump the nft ruleset and tc script
- UI (`ui/`, bun): `bun run kit` (regenerate `public/city-kit.glb` with Blender), `bun test`, `bun run dev` (browser + mock daemon, `?mock=city`), `bunx tauri build --no-bundle` (binary in `target/release/deepwork-ui`)
- Kernel-level checks without touching the host: `unshare -rn sh -c 'nft -f file'` (user + net namespace)

## Rules

- Never apply nft/tc/resolved changes on the host or install the service without the user's explicit go-ahead.
- All policy and state live in `deepworkd`; clients are untrusted views.
- Keep the safety rails in PLAN.md (6h `MAX_SESSION`, surrender, fail-open PAM, TTY root) intact.
- nft/tc rendering stays pure (in `enforcer/nft.rs`, `enforcer/tc.rs`) and unit tested; only `enforcer/mod.rs` runs commands.
- The user's resolved uses strict DNS-over-TLS (NextDNS). Anything touching DNS must keep working with that.
