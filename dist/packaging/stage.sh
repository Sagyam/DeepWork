#!/usr/bin/env bash
# Lays out a built tree as it is installed by the .deb, the .rpm and the
# tarball: everything in /usr, like the Arch package (dist/PKGBUILD).
#
#   cargo build --release --locked
#   (cd ui && bun install --frozen-lockfile && bun run build)
#   cargo build --release --locked -p deepwork-ui --features custom-protocol
#   dist/packaging/stage.sh target/pkg/stage
#
# The config is shipped as an example and seeded by postinstall.sh, not as a
# package config file: the app rewrites /etc/deepwork/config.toml, and dpkg
# would stop upgrades to ask about it.
set -euo pipefail
cd "$(dirname "$0")/../.."

dest=${1:?usage: stage.sh DESTDIR}
bin=${CARGO_TARGET_DIR:-target}/release
rm -rf "$dest"

# Same rewrite as prepare() in the PKGBUILD: the sources carry /usr/local
# paths for dist/install.sh.
usr() {
    sed -e 's|/usr/local/bin|/usr/bin|g' \
        -e 's|/usr/local/lib/deepwork|/usr/lib/deepwork|g' \
        -e 's|/usr/local/share/doc|/usr/share/doc|g' "$1"
}
put() { # mode, source (stdin if -), destination
    install -d "$dest$(dirname "$3")"
    if [[ $2 == - ]]; then cat >"$dest$3"; else cp "$2" "$dest$3"; fi
    chmod "$1" "$dest$3"
}

for b in deepworkd deepwork deepwork-agent deepwork-ui; do
    put 755 "$bin/$b" "/usr/bin/$b"
done
put 755 "$bin/deepwork-pam-gate" /usr/lib/deepwork/deepwork-pam-gate

usr dist/deepworkd.service | put 644 - /usr/lib/systemd/system/deepworkd.service
usr dist/deepwork-agent.service | put 644 - /usr/lib/systemd/user/deepwork-agent.service
usr dist/10-deepwork.rules | put 644 - /usr/share/polkit-1/rules.d/10-deepwork.rules
usr dist/deepwork-ui.desktop | put 644 - /usr/share/applications/deepwork-ui.desktop
usr dist/pam.py | put 755 - /usr/share/deepwork/pam.py
put 644 ui/src-tauri/icons/icon.png /usr/share/icons/hicolor/512x512/apps/deepwork.png
put 644 dist/config.example.toml /usr/share/deepwork/config.example.toml
put 644 dist/packaging/apt-browser-policies.conf /usr/share/deepwork/apt-browser-policies.conf

put 644 docs/PLAN.md /usr/share/doc/deepwork/PLAN.md
put 644 README.md /usr/share/doc/deepwork/README.md
put 644 LICENSE /usr/share/doc/deepwork/LICENSE

# The scriptlets, for the tarball's install.sh (packages embed their own).
for s in postinstall preremove postremove; do
    put 755 "dist/packaging/$s.sh" "/usr/share/deepwork/$s.sh"
done
