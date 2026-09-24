#!/bin/zsh
# Optional, one-time setup. Downloads the official portable engine locally.
set -eu
PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"
mkdir -p .tools
RELEASE_BASE="https://github.com/godotengine/godot-builds/releases/download/4.5.1-stable"
ARCHIVE="Godot_v4.5.1-stable_macos.universal.zip"
curl -fL --retry 2 "$RELEASE_BASE/$ARCHIVE" -o ".tools/$ARCHIVE"
curl -fL --retry 2 "$RELEASE_BASE/SHA512-SUMS.txt" -o .tools/SHA512-SUMS.txt
cd .tools
awk '$2 == "Godot_v4.5.1-stable_macos.universal.zip" {print}' SHA512-SUMS.txt > verify.sha512
test -s verify.sha512
shasum -a 512 -c verify.sha512
ditto -x -k "$ARCHIVE" .
echo "Ready. Open Play.command to play, or Edit.command to learn in the editor."
