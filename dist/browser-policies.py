#!/usr/bin/env python3
"""Turn off browser DNS-over-HTTPS with managed policies, so lookups go through
the system resolver (and so through deepworkd during a session).

    sudo python3 -I dist/browser-policies.py apply
    sudo python3 -I dist/browser-policies.py remove

Firefox-family browsers: merges a locked DNSOverHTTPS policy into
distribution/policies.json. Chromium-family browsers: writes deepwork.json into
the managed policy directory. Browsers must be restarted to pick these up.
"""

import glob
import json
import os
import sys

FIREFOX_DISTRIBUTION_DIRS = [
    *glob.glob("/opt/zen-browser*/distribution"),
    "/usr/lib/zen-browser/distribution",
    "/usr/lib/firefox/distribution",
]
CHROMIUM_POLICY_DIRS = [
    "/etc/chromium/policies/managed",
    "/etc/opt/chrome/policies/managed",
    "/etc/brave/policies/managed",
]
FIREFOX_POLICY = {"Enabled": False, "Locked": True}
CHROMIUM_POLICY = {"DnsOverHttpsMode": "off"}


def firefox(apply: bool) -> None:
    for dist in FIREFOX_DISTRIBUTION_DIRS:
        app_dir = os.path.dirname(dist)
        if not os.path.isdir(app_dir):
            continue
        path = os.path.join(dist, "policies.json")
        data = {"policies": {}}
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
        policies = data.setdefault("policies", {})
        if apply:
            policies["DNSOverHTTPS"] = FIREFOX_POLICY
        elif policies.get("DNSOverHTTPS") == FIREFOX_POLICY:
            del policies["DNSOverHTTPS"]
        else:
            continue
        os.makedirs(dist, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        print(f"{'set' if apply else 'removed'} DNSOverHTTPS policy in {path}")


def chromium(apply: bool) -> None:
    for managed in CHROMIUM_POLICY_DIRS:
        browser_dir = os.path.dirname(os.path.dirname(managed))
        path = os.path.join(managed, "deepwork.json")
        if apply and os.path.isdir(browser_dir):
            os.makedirs(managed, exist_ok=True)
            with open(path, "w") as f:
                json.dump(CHROMIUM_POLICY, f, indent=2)
                f.write("\n")
            print(f"wrote {path}")
        elif not apply and os.path.exists(path):
            os.remove(path)
            print(f"removed {path}")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("apply", "remove"):
        print(__doc__, file=sys.stderr)
        return 2
    apply = sys.argv[1] == "apply"
    firefox(apply)
    chromium(apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
