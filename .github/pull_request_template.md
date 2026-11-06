## What and why

<!-- What this changes, and the problem it solves. "Closes #123" links an issue. -->

## How I tested it

<!-- Commands run, distribution, and for UI changes a screenshot from `bun run dev`. -->

## Checklist

- [ ] `cargo fmt`, `cargo clippy --all-targets`, `cargo test` and `cd ui && bun test` pass
- [ ] Nothing was applied to my host's nft/tc/resolved while testing, or I meant it to be
- [ ] nft/tc rendering stays pure and unit tested (`enforcer/nft.rs`, `enforcer/tc.rs`)
- [ ] Safety rails intact: 6 hour cap, surrender, fail-open PAM, TTY root
- [ ] Works with systemd-resolved in strict DNS-over-TLS mode (if it touches DNS)
- [ ] Removed the item from `docs/ROADMAP.md` and updated the doc for the area (if any)
