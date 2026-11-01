#!/usr/bin/env bash
# Installs deepworkd as a system service. Works from any directory:
#   ./dist/install.sh            install / upgrade
#   ./dist/install.sh uninstall  remove (only when no session is running)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ${1:-} == uninstall ]]; then
    sudo systemctl disable --now deepworkd.service || true
    systemctl --user disable --now deepwork-agent.service || true
    sudo rm -f /etc/systemd/system/deepworkd.service /usr/local/bin/deepworkd /usr/local/bin/deepwork \
        /usr/local/bin/deepwork-agent /etc/systemd/user/deepwork-agent.service
    sudo systemctl daemon-reload
    # The daemon lifts enforcement when a session ends; this covers a crash.
    sudo nft destroy table inet deepwork 2>/dev/null || true
    sudo python3 -I dist/browser-policies.py remove
    if [[ -f /run/systemd/resolved.conf.d/zz-deepwork.conf ]]; then
        sudo rm -f /run/systemd/resolved.conf.d/zz-deepwork.conf
        sudo systemctl restart systemd-resolved
    fi
    echo "Removed. Config and history are left in /etc/deepwork and /var/lib/deepwork."
    exit 0
fi

cargo build --release --locked
sudo install -Dm755 target/release/deepworkd /usr/local/bin/deepworkd
sudo install -Dm755 target/release/deepwork /usr/local/bin/deepwork
sudo install -Dm755 target/release/deepwork-agent /usr/local/bin/deepwork-agent
sudo install -Dm644 dist/deepwork-agent.service /etc/systemd/user/deepwork-agent.service
sudo install -Dm644 dist/deepworkd.service /etc/systemd/system/deepworkd.service
sudo install -Dm644 docs/PLAN.md /usr/local/share/doc/deepwork/PLAN.md
if [[ -f dist/config.local.toml ]]; then
    sudo install -Dm644 dist/config.local.toml /etc/deepwork/config.toml
elif [[ ! -f /etc/deepwork/config.toml ]]; then
    sudo install -Dm644 dist/config.example.toml /etc/deepwork/config.toml
    echo "Installed /etc/deepwork/config.toml from the example. Review it."
fi
# Browsers must resolve through the system resolver, not their own DoH.
sudo python3 -I dist/browser-policies.py apply
echo "Restart Zen / Chromium so the DNS-over-HTTPS policy takes effect."
sudo deepworkd --print-rules >/dev/null  # validates the config
sudo systemctl daemon-reload
sudo systemctl enable deepworkd.service
# Type=notify: returns once the daemon's socket is up.
sudo systemctl restart deepworkd.service
# Notifications run in the user's graphical session.
systemctl --user daemon-reload
systemctl --user enable deepwork-agent.service
systemctl --user restart deepwork-agent.service
deepwork status
