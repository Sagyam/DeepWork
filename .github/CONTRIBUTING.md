# Contributing to DeepWork

Thanks for helping. Bug reports, fixes, distro packaging and new countermeasures
are all welcome.

## Before you start

- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) covers the design and threat
  model, [docs/ROADMAP.md](../docs/ROADMAP.md) what is planned. Read them
  before proposing a feature.
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
- If your change lands a roadmap item, delete it from `docs/ROADMAP.md` and
  update the doc for that area (see "Writing docs" in `CLAUDE.md`).

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
possible. Open a regular issue, and check the threat model in ARCHITECTURE.md first.
Privilege escalation, or anything that could lock a user out, is different:
see [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your work is released under the
[MIT License](../LICENSE).
