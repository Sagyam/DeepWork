# Contributing to DeepWork

Thanks for helping. Bug reports, fixes, distro packaging and new countermeasures
are all welcome.

## Before you start

- [docs/PLAN.md](../docs/PLAN.md) is the source of truth: design, threat model
  and roadmap. Read it before proposing a feature.
- [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) covers the layout, building
  without root and the mock UI.
- For anything bigger than a small fix, open an issue first so we can agree on
  the approach.

## Develop

Nothing here needs root. The daemon has a dry run that logs commands instead of
running them:

```sh
cargo run -p deepworkd -- --dry-run
cargo run -p deepworkd -- --print-rules      # the exact nft ruleset and tc script
cd ui && bun run dev                         # then open http://localhost:5173/?mock=city
```

To check an nft ruleset against a real kernel without touching your host:

```sh
unshare -rn sh -c 'nft -f ruleset.nft'
```

## Before you open a pull request

```sh
cargo fmt
cargo clippy --all-targets
cargo test
cd ui && bun test
```

- Keep nft/tc rendering pure (`enforcer/nft.rs`, `enforcer/tc.rs`) and unit
  tested; only `enforcer/mod.rs` runs commands.
- All policy and state live in `deepworkd`. The CLI, agent and UI are untrusted
  views.
- Anything touching DNS must keep working with systemd-resolved in strict
  DNS-over-TLS mode.
- If your change lands a PLAN.md checklist item, tick it.

## Safety rails

These protect people from locking themselves out of their own machine. Pull
requests that weaken them won't be merged:

- Sessions are capped at 6 hours (`MAX_SESSION`).
- Surrender always works.
- The PAM hook fails open.
- TTY root login is always the emergency exit.

## Bypasses

Found a way around the throttle? That is useful, but usually not a security
issue: the user has the sudo password, so a determined bypass is always
possible. Open a regular issue, and check the threat model in PLAN.md first.
Privilege escalation, or anything that could lock a user out, is different:
see [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your work is released under the
[MIT License](../LICENSE).
