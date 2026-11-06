# DeepWork

Focus app for Linux (Omarchy/Arch, Hyprland). A root daemon throttles
distracting sites at the network layer during sessions; focus builds a 3D
city, giving in damages it.

## Docs

Read `docs/ROADMAP.md` first: it says what to work on next.

| File | Holds |
|---|---|
| `docs/ROADMAP.md` | Open work only: next steps, host checks, backlog, ideas |
| `docs/ARCHITECTURE.md` | Daemon, enforcement, threat model, safety rails |
| `docs/GAME.md` | Progression rules (coins, needs, blueprints, penalties) |
| `docs/APP.md` | Tauri app, city renderer, model catalogue, performance lessons |
| `docs/DEVELOPMENT.md` | Commands: build, mock UI, viewers, benches, install, release |
| `docs/DESIGN.md` | Visual design language shared with the site and other apps; UI follows it, light and dark |
| `README.md` | Short visual pitch for passersby (media in `assets/`) |

## Commands

- `cargo test`, `cargo clippy --all-targets`, `cargo fmt`
- `cargo run -p deepworkd -- --dry-run` (commands logged, not run), `--print-rules`
- `cd ui`: `bun test`, `bun run dev` (`?mock=city`), `bun run models`, `bunx tauri build --no-bundle`
- Kernel checks without touching the host: `unshare -rn sh -c 'nft -f file'`

More in `docs/DEVELOPMENT.md`.

## Rules

- Never apply nft/tc/resolved changes on the host or install the service without the user's explicit go-ahead.
- All policy and state live in `deepworkd`; clients are untrusted views.
- Keep the safety rails (6h `MAX_SESSION`, surrender, fail-open PAM, TTY root) intact.
- nft/tc rendering stays pure (`enforcer/nft.rs`, `enforcer/tc.rs`) and unit tested; only `enforcer/mod.rs` runs commands.
- The user's resolved uses strict DNS-over-TLS (NextDNS). Anything touching DNS must keep working with that.
- `ui/src/proto.ts` mirrors `crates/proto` by hand; change both.

## Writing docs

The docs were once 200 KB of dated diary entries nobody could read. Keep
them small enough to read in one sitting.

- **Describe the present.** Docs say how things are, not how they got
  there. No dates on facts, no "followed the same day", no "used to".
  The story goes in the commit message and PR description.
- **One home per fact.** Put it in the file from the table above and link
  to it from elsewhere. Never copy a paragraph into a second file.
- **Code is the source for numbers.** Name the constant or file
  (`LENGTH_BANDS` in `world.rs`) rather than copying values that will drift.
  Write a number only when it's a decision or a measurement worth keeping.
- **Done work leaves the roadmap.** Delete the item; don't tick it and
  leave it, or strike it through. If readers need to know about the result,
  add it to the topic doc in a line or two.
- **Write for someone skimming.** Lead with the point. Short sections,
  tables for catalogues, one line per item. No table cell longer than a
  sentence; no paragraph longer than five lines.
- **Leave out**: how you verified something (that goes in the PR), what a
  model looks like brick by brick (that's the code), effort estimates, and
  ideas already rejected, unless the reason stops someone retrying them
  (then one line under "Decisions").
- **Keep a decision with its reason, in one line**, in the topic doc's
  Decisions section or next to the rule it explains.
- **Budget**: a doc over ~300 lines needs cutting or splitting by topic.
  Before you add a section, look for one to merge, shorten or delete.
- When you finish a task: update the doc for the area you changed, remove
  the roadmap item, and reread your edit as a newcomer would.
