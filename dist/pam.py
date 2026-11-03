#!/usr/bin/env python3
"""Hook the DeepWork gate into PAM so sudo, su and polkit authentication are
refused during a focus session.

    sudo python3 -I dist/pam.py apply   [--root DIR]
    sudo python3 -I dist/pam.py remove  [--root DIR]

The block fails open by construction: pam_deny is only reached when the gate
exits 0, which it does only when the daemon explicitly says "deny". A missing
gate binary, a crash, a timeout or a stopped daemon all skip pam_deny. Root
(and so TTY root login, which uses the `login` service) is never gated.

Services configured only in /usr/lib/pam.d (openSUSE) get a hooked copy in
/etc/pam.d, which takes precedence; removal deletes that copy again.
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
        # openSUSE and others ship PAM files in /usr/lib/pam.d; PAM reads a
        # file of the same name in /etc/pam.d instead, so the hook goes in a
        # copy there, which is deleted again on removal.
        vendor = os.path.join(root, "usr/lib/pam.d", service)
        vendor_text = None
        if os.path.isfile(vendor):
            with open(vendor) as f:
                vendor_text = f.read()
        if os.path.isfile(path):
            with open(path) as f:
                old = f.read()
            mode = os.stat(path).st_mode & 0o7777
        elif apply and vendor_text is not None:
            old, mode = vendor_text, 0o644
        else:
            continue
        new = edit(old, apply)
        if not apply and vendor_text is not None and new != old and new == edit(vendor_text, False):
            os.remove(path)
            print(f"unhooked {path} (removed; {vendor} applies again)")
            continue
        if new == old and os.path.isfile(path):
            continue
        tmp = path + ".deepwork-tmp"
        with open(tmp, "w") as f:
            f.write(new)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        print(f"{'hooked' if apply else 'unhooked'} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
