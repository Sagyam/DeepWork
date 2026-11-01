#!/usr/bin/env python3
"""Hook the DeepWork gate into PAM so sudo, su and polkit authentication are
refused during a focus session.

    sudo python3 -I dist/pam.py apply   [--root DIR]
    sudo python3 -I dist/pam.py remove  [--root DIR]

The block fails open by construction: pam_deny is only reached when the gate
exits 0, which it does only when the daemon explicitly says "deny". A missing
gate binary, a crash, a timeout or a stopped daemon all skip pam_deny. Root
(and so TTY root login, which uses the `login` service) is never gated.
"""

import os
import sys

GATE = "/usr/local/lib/deepwork/deepwork-pam-gate"
SERVICES = ["sudo", "sudo-i", "su", "su-l", "polkit-1"]
BEGIN = "# BEGIN deepwork: no root during focus sessions (fails open)"
END = "# END deepwork"
EXEC = f"pam_exec.so quiet quiet_log stdout {GATE}"


def block() -> list[str]:
    lines = [BEGIN]
    for stage in ("auth", "account"):
        lines.append(f"{stage:<8} [success=ignore default=1] {EXEC}")
        lines.append(f"{stage:<8} requisite pam_deny.so")
    lines.append(END)
    return lines


def strip(lines: list[str]) -> list[str]:
    out, inside = [], False
    for line in lines:
        if line.strip() == BEGIN:
            inside = True
        elif inside and line.strip() == END:
            inside = False
        elif not inside:
            out.append(line)
    return out


def edit(text: str, apply: bool) -> str:
    lines = strip(text.splitlines())
    if apply:
        # After the `#%PAM-1.0` header, before every other rule.
        at = 1 if lines and lines[0].startswith("#%PAM") else 0
        lines[at:at] = block()
    return "\n".join(lines) + "\n"


def main() -> int:
    args = sys.argv[1:]
    root = "/"
    if len(args) == 3 and args[1] == "--root":
        root = args[2]
        args = args[:1]
    if len(args) != 1 or args[0] not in ("apply", "remove"):
        print(__doc__, file=sys.stderr)
        return 2
    apply = args[0] == "apply"
    if apply and root == "/" and not os.access(GATE, os.X_OK):
        print(f"{GATE} is missing; install it before hooking PAM", file=sys.stderr)
        return 1
    for service in SERVICES:
        path = os.path.join(root, "etc/pam.d", service)
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            old = f.read()
        new = edit(old, apply)
        if new == old:
            continue
        tmp = path + ".deepwork-tmp"
        with open(tmp, "w") as f:
            f.write(new)
        os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        os.replace(tmp, path)
        print(f"{'hooked' if apply else 'unhooked'} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
