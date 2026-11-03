#!/bin/sh
# DeepWork from the release tarball, for systemd distributions without a
# package here. Prefer the .deb, .rpm or Arch package when there is one: they
# upgrade and uninstall cleanly through the package manager.
#
#   sudo ./install.sh             install or upgrade into /usr
#   sudo ./install.sh uninstall   remove (settings and history are kept)
set -eu
cd "$(dirname "$0")"

manifest=/usr/share/deepwork/MANIFEST
if [ "$(id -u)" != 0 ]; then
    echo "Run as root: sudo $0 ${1:-}" >&2
    exit 1
fi

if [ "${1:-}" = uninstall ]; then
    [ -f "$manifest" ] || { echo "DeepWork was not installed from a tarball." >&2; exit 1; }
    sh /usr/share/deepwork/preremove.sh 0
    xargs rm -f <"$manifest"
    rm -f "$manifest" /etc/apt/apt.conf.d/80deepwork-browser-policies
    rmdir /usr/share/deepwork /usr/lib/deepwork /usr/share/doc/deepwork 2>/dev/null || true
    systemctl daemon-reload >/dev/null 2>&1 || true
    exit 0
fi

for cmd in nft tc python3 systemctl; do
    command -v "$cmd" >/dev/null || echo "warning: $cmd not found; install it before starting deepworkd" >&2
done

[ -f "$manifest" ] && step=2 || step=1
find usr -type f | sed 's|^|/|' >manifest.new
cp -R usr /
install -Dm644 manifest.new "$manifest"
rm -f manifest.new
[ -d /etc/apt/apt.conf.d ] &&
    install -m644 /usr/share/deepwork/apt-browser-policies.conf /etc/apt/apt.conf.d/80deepwork-browser-policies
sh /usr/share/deepwork/postinstall.sh "$step"
