#!/bin/sh
# Installs the latest DeepWork release with the system's package manager:
#
#   curl -fsSL https://raw.githubusercontent.com/Sagyam/DeepWork/main/dist/get.sh | sh
#
# Debian / Ubuntu get the .deb, Fedora / openSUSE the .rpm, Arch the pacman
# package, anything else with systemd the tarball. DEEPWORK_VERSION=v0.2.0
# picks a release; DEEPWORK_NO_ENABLE=1 skips starting the services.
set -eu

repo=Sagyam/DeepWork
say() { printf '\033[1m%s\033[0m\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = Linux ] || die "DeepWork runs on Linux only (nftables, tc and PAM)."
[ -d /run/systemd/system ] || die "DeepWork needs systemd as the init system."
command -v curl >/dev/null || die "curl is required."

case "$(uname -m)" in
    x86_64 | amd64) arch=x86_64 debarch=amd64 ;;
    aarch64 | arm64) arch=aarch64 debarch=arm64 ;;
    *) die "no build for $(uname -m); build from source (docs/DEVELOPMENT.md)." ;;
esac

if [ "$(id -u)" = 0 ]; then sudo=; else
    command -v sudo >/dev/null || die "run as root, or install sudo."
    sudo=sudo
fi

# Root is locked during a session, and the daemon refuses to stop anyway.
if command -v deepwork >/dev/null &&
    deepwork status --json 2>/dev/null | grep -q '^{"type":"status","session":{'; then
    die "a focus session is running; upgrade after it ends."
fi

. /etc/os-release
family=other
for id in ${ID:-} ${ID_LIKE:-}; do
    case "$id" in
        debian | ubuntu) family=deb; break ;;
        fedora | rhel | centos | suse | opensuse*) family=rpm; break ;;
        arch) family=arch; break ;;
    esac
done
[ "$family" = arch ] && [ "$arch" != x86_64 ] && family=other

case "$family" in
    deb) pattern="_$debarch\.deb" ;;
    rpm) pattern="\.$arch\.rpm" ;;
    arch) pattern="-$arch\.pkg\.tar\.zst" ;;
    other) pattern="-$arch-linux\.tar\.gz" ;;
esac

if [ -n "${DEEPWORK_VERSION:-}" ]; then
    api="https://api.github.com/repos/$repo/releases/tags/$DEEPWORK_VERSION"
else
    api="https://api.github.com/repos/$repo/releases/latest"
fi
release=$(curl -fsSL "$api") ||
    die "no release found at $api (none published yet, or GitHub rate-limited this address)."
urls=$(printf '%s\n' "$release" | grep -o '"browser_download_url": *"[^"]*"' | sed 's/.*"\(https[^"]*\)"/\1/')
url=$(printf '%s\n' "$urls" | grep -E "$pattern\$" | grep -v -- '-debug' | head -n1)
sums=$(printf '%s\n' "$urls" | grep -E '/SHA256SUMS$' | head -n1)
[ -n "$url" ] || die "the release has no asset matching $pattern."

tmp=$(mktemp -d)
chmod 755 "$tmp" # apt reads the .deb as its sandbox user
trap 'rm -rf "$tmp"' EXIT
file="$tmp/${url##*/}"
say "Downloading ${url##*/}"
curl -fL --progress-bar -o "$file" "$url"
if [ -n "$sums" ]; then
    curl -fsSL -o "$tmp/SHA256SUMS" "$sums"
    (cd "$tmp" && grep " ${url##*/}\$" SHA256SUMS | sha256sum -c --quiet -) ||
        die "checksum mismatch for ${url##*/}."
fi

say "Installing"
case "$family" in
    deb) $sudo apt-get install -y "$file" ;;
    rpm)
        if command -v dnf >/dev/null; then
            $sudo dnf install -y "$file"
        elif command -v zypper >/dev/null; then
            # Release packages are not signed yet.
            $sudo zypper --non-interactive install --allow-unsigned-rpm "$file"
        else
            die "neither dnf nor zypper found."
        fi
        ;;
    arch) $sudo pacman -U --noconfirm "$file" ;;
    other)
        tar -xzf "$file" -C "$tmp"
        $sudo sh "$tmp"/deepwork-*/install.sh
        ;;
esac

if [ -n "${DEEPWORK_NO_ENABLE:-}" ]; then exit 0; fi
say "Starting the daemon and the notification agent"
$sudo systemctl enable --now deepworkd.service
if [ -n "$sudo" ] && systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user enable --now deepwork-agent.service || true
else
    echo "As your user: systemctl --user enable --now deepwork-agent.service"
fi
say "Done. Try: deepwork start 25m, or open DeepWork from the app launcher."
