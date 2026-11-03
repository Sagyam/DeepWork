#!/bin/sh
# Runs as root before the package's files go. dpkg passes `remove` (or
# `upgrade`), rpm passes 0 on removal and 1 on upgrade. Only a removal undoes
# anything. Mirrors pre_remove in dist/deepwork-git.install.

case "$1" in
    remove | 0) ;;
    *) exit 0 ;;
esac

# Unhook PAM first, so sudo never points at a missing gate.
if [ -f /usr/share/deepwork/pam.py ]; then
    python3 -I /usr/share/deepwork/pam.py remove >/dev/null 2>&1 ||
        echo 'warning: could not unhook PAM; check /etc/pam.d/sudo'
fi

cleanup() {
    /usr/bin/deepworkd --browser-policies remove >/dev/null 2>&1 || true
    nft destroy table inet deepwork >/dev/null 2>&1 || true
}

if systemctl is-active --quiet deepworkd.service 2>/dev/null; then
    # Refused during a session; the safety rail wins over a clean removal.
    if systemctl stop deepworkd.service >/dev/null 2>&1; then
        cleanup
        if [ -e /run/systemd/resolved.conf.d/zz-deepwork.conf ]; then
            rm -f /run/systemd/resolved.conf.d/zz-deepwork.conf
            systemctl restart systemd-resolved.service >/dev/null 2>&1 || true
        fi
    else
        echo 'warning: a focus session is running; deepworkd stays up until it ends or the machine reboots'
    fi
else
    cleanup
fi
systemctl disable deepworkd.service >/dev/null 2>&1 || true

echo 'note: settings and history are kept in /etc/deepwork and /var/lib/deepwork'
