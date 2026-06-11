#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$ROOT/VERSION" 2>/dev/null || printf 'unknown')"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$BIN_DIR" "$APP_DIR"
cat > "$BIN_DIR/timeline-builder" <<EOF
#!/usr/bin/env bash
exec python3 "$ROOT/tools/timeline_builder_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/timeline-builder"
cat > "$APP_DIR/timeline-builder.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Timeline Builder
Comment=Build editable draw.io timelines from Jira CSV exports
Exec=$BIN_DIR/timeline-builder %f
Terminal=false
Categories=Office;Utility;
EOF
cat > "$BIN_DIR/timeline-nautilus-actions" <<EOF
#!/usr/bin/env bash
exec python3 "$ROOT/tools/nautilus_actions_gui.py" "\$@"
EOF
chmod +x "$BIN_DIR/timeline-nautilus-actions"
cat > "$APP_DIR/timeline-nautilus-actions.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Nautilus Actions Manager
Comment=Edit generic Nautilus custom actions
Exec=$BIN_DIR/timeline-nautilus-actions
Terminal=false
Categories=Settings;Utility;
EOF
update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
echo "Installed Timeline Builder launcher v$VERSION"
echo "Launcher: $BIN_DIR/timeline-builder"
echo "Target:   $ROOT/tools/timeline_builder_gui.py"
echo "Installed Nautilus Actions Manager launcher: $BIN_DIR/timeline-nautilus-actions"
