#!/usr/bin/env bash
set -euo pipefail

EXT_FILE="$HOME/.local/share/nautilus-python/extensions/nautilus_custom_actions.py"
BIN_FILE="$HOME/.local/bin/nca-settings"
DESKTOP_FILE="$HOME/.local/share/applications/nautilus-custom-actions-settings.desktop"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nautilus-custom-actions"

rm -f "$EXT_FILE" "$BIN_FILE" "$DESKTOP_FILE"
nautilus -q >/dev/null 2>&1 || true

echo "Uninstalled the extension and settings command."
echo "Your config was left in place: $CONFIG_DIR"
echo "Delete it manually if you no longer want it."
