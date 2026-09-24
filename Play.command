#!/bin/zsh
set -e
PROJECT_DIR="${0:A:h}"
GODOT_BIN="$PROJECT_DIR/.tools/Godot.app/Contents/MacOS/Godot"
if [[ ! -x "$GODOT_BIN" ]]; then
  GODOT_BIN="/Applications/Godot.app/Contents/MacOS/Godot"
fi
if [[ ! -x "$GODOT_BIN" ]]; then
  echo "Godot was not found. Run Setup.command once, then open Play.command again."
  read -k 1 "?Press any key to close."
  exit 1
fi
exec "$GODOT_BIN" --path "$PROJECT_DIR"
