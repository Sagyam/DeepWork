#!/bin/sh
# Renders the app icons from assets/logo.svg: sh scripts/icon.sh (needs rsvg-convert)
set -eu
here=$(dirname "$0")
logo="$here/../../assets/logo.svg"
out="$here/../src-tauri/icons"
for spec in 32x32.png:32 128x128.png:128 icon.png:512; do
    rsvg-convert -w "${spec#*:}" -h "${spec#*:}" -o "$out/${spec%%:*}" "$logo"
done
