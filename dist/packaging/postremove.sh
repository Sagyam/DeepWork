#!/bin/sh
# Runs as root after the package's files are gone. `dpkg --purge` also drops
# the config the package seeded (history in /var/lib/deepwork stays).
systemctl daemon-reload >/dev/null 2>&1 || true
if [ "$1" = purge ]; then
    rm -rf /etc/deepwork
fi
exit 0
