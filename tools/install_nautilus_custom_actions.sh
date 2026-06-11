#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NCA_DIR="$ROOT/tools/nautilus-custom-actions"

if [[ ! -d "$NCA_DIR" ]]; then
  echo "ERROR: Missing vendored Nautilus helper folder:" >&2
  echo "$NCA_DIR" >&2
  exit 1
fi

bash "$NCA_DIR/install.sh" "$@"
