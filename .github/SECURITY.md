# Security Policy

`deepworkd` runs as root, rewrites the firewall and answers DNS, so security
bugs here matter. Thanks for reporting them responsibly.

## Supported versions

Only the [latest release](https://github.com/Sagyam/DeepWork/releases/latest)
and `main` get security fixes.

## Reporting a vulnerability

**Don't open a public issue.** Report it privately through
[GitHub's vulnerability reporting](https://github.com/Sagyam/DeepWork/security/advisories/new).

Include the version, your distribution, steps to reproduce and what an attacker
gains. You should hear back within a week. Once a fix is released, the advisory
is published and you are credited unless you'd rather not be.

## In scope

- Privilege escalation: an unprivileged user or process getting root, or
  making the daemon act for them beyond what the IPC protocol allows
- Another local user controlling or reading someone else's sessions
- Memory safety bugs or crashes in the DNS forwarder or SNI inspection that
  a network peer can trigger
- Anything that can lock a user out of their machine: sessions past
  `MAX_SESSION`, a surrender that can't complete, a PAM hook that fails closed,
  or blocking TTY root login
- Network enforcement that outlives a session, or breaks DNS for good
- Tampering with release artifacts, `get.sh` or the packaging scripts

## Out of scope

- Bypassing the throttle as the user who owns the machine. The threat model in
  [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md#threat-model) accepts that someone with the
  sudo password can always get around it. Report bypasses as regular issues.
- Attacks that need physical access, a live USB or a modified kernel
