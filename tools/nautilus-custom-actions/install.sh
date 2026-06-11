#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nautilus-custom-actions"

install_deps=true
if [[ "${1:-}" == "--no-deps" ]]; then
  install_deps=false
fi

if [[ "$install_deps" == true ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing dependencies: python3-nautilus python3-gi"
    sudo apt-get update
    sudo apt-get install -y python3-nautilus python3-gi
  else
    echo "apt-get not found. Install python3-nautilus and python3-gi manually, then re-run with --no-deps."
    exit 1
  fi
fi

mkdir -p "$EXT_DIR" "$BIN_DIR" "$APP_DIR" "$CONFIG_DIR"
cp "$ROOT/custom_actions.py" "$EXT_DIR/nautilus_custom_actions.py"
cp "$ROOT/nca-settings" "$BIN_DIR/nca-settings"
chmod +x "$BIN_DIR/nca-settings"

if [[ ! -f "$CONFIG_DIR/actions.json" ]]; then
  cp "$ROOT/sample_actions.json" "$CONFIG_DIR/actions.json"
fi

cat > "$APP_DIR/nautilus-custom-actions-settings.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Nautilus Custom Actions Settings
Comment=Configure right-click actions in GNOME Files/Nautilus
Exec=$BIN_DIR/nca-settings
Terminal=true
Categories=Settings;Utility;
DESKTOP

update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

# Restart Nautilus so it loads the extension.
nautilus -q >/dev/null 2>&1 || true

echo "Installed."
echo "Run settings with: $BIN_DIR/nca-settings"
echo "Config file: $CONFIG_DIR/actions.json"
echo "Right-click a file in Files/Nautilus after it restarts."
