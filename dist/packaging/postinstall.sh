#!/bin/sh
# Runs as root once the .deb, .rpm or tarball is unpacked. dpkg passes
# `configure <old version>` (empty on a first install), rpm passes 1 on
# install and 2 on upgrade; the tarball's install.sh does the same as rpm.
# Mirrors post_install / post_upgrade in dist/deepwork-git.install.

case "$1" in
    configure) upgrade=$2 ;;
    1) upgrade= ;;
    *) upgrade=yes ;;
esac

systemctl daemon-reload >/dev/null 2>&1 || true

# The app owns this file once installed; never overwrite it.
if [ ! -e /etc/deepwork/config.toml ]; then
    install -Dm644 /usr/share/deepwork/config.example.toml /etc/deepwork/config.toml
fi

# pam_exec asks the daemon and fails open, so a missing gate or a stopped
# daemon never locks anyone out of sudo. Idempotent, and re-run on upgrades in
# case a sudo or polkit update restored /etc/pam.d.
if [ -x /usr/lib/deepwork/deepwork-pam-gate ]; then
    python3 -I /usr/share/deepwork/pam.py apply >/dev/null ||
        echo 'warning: could not hook PAM; run: sudo python3 -I /usr/share/deepwork/pam.py apply'
fi

if [ -n "$upgrade" ]; then
    # A running session sets RefuseManualStop, so this fails and the old
    # daemon keeps enforcing. Otherwise the new binary takes over now.
    systemctl try-restart deepworkd.service >/dev/null 2>&1 ||
        echo 'note: deepworkd was not restarted (a session may be running); it will use the new build after the session ends or at reboot'
    exit 0
fi

cat <<'MSG'
DeepWork is installed. To put it to work:

  sudo systemctl enable --now deepworkd.service          # the daemon (root)
  systemctl --user enable --now deepwork-agent.service   # notifications
  deepwork start 25m                                     # a first session

  deepwork-ui                         opens the city and the settings sheet
  /etc/deepwork/config.toml           settings (the app edits this for you)
  /usr/share/doc/deepwork/PLAN.md     how it works and what it enforces

sudo, pkexec and systemctl are refused while a session runs (PAM and polkit
hooks, both fail open; TTY root always works). Removing the package removes
the hooks. To undo them now:
  sudo python3 -I /usr/share/deepwork/pam.py remove
MSG
