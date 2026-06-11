#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INPUT="${1:-${NCA_PATH:-}}"
STABLE_LAUNCHER="$HOME/.local/bin/timeline-builder"
if [[ -x "$STABLE_LAUNCHER" && "${TIMELINE_BUILDER_FORCE_REPO:-0}" != "1" ]]; then
  exec "$STABLE_LAUNCHER" ${INPUT:+"$INPUT"}
fi
if [[ -n "$INPUT" ]]; then
  exec python3 "$REPO_DIR/tools/timeline_builder_gui.py" "$INPUT"
fi
exec python3 "$REPO_DIR/tools/timeline_builder_gui.py"
