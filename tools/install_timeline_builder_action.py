#!/usr/bin/env python3
"""Install the optional Nautilus launcher action for Timeline Builder."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "nautilus-custom-actions"
CONFIG_PATH = APP_DIR / "actions.json"

TIMELINE_LABELS = {
    "Timeline: Open in Timeline Builder",
    "Timeline: Add source_row to CSV",
    "Timeline: Prepare AI review packet",
    "Timeline: Generate timeline JSON from Jira CSV",
    "Timeline: Generate draw.io from Jira CSV",
    "Timeline: Sanity Check JSON",
    "Timeline: Render draw.io",
}


def load_config() -> dict[str, Any]:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        return {"actions": []}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {"actions": []}
    if not isinstance(data, dict):
        data = {"actions": []}
    if not isinstance(data.get("actions"), list):
        data["actions"] = []
    return data


def save_config(data: dict[str, Any]) -> Path | None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    backup = None
    if CONFIG_PATH.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = CONFIG_PATH.with_name(f"actions.json.bak.{timestamp}")
        backup.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CONFIG_PATH)
    return backup


def main() -> int:
    stable_launcher = Path.home() / ".local" / "bin" / "timeline-builder"
    launcher = stable_launcher if stable_launcher.exists() else ROOT / "scripts" / "context_open_timeline_builder.sh"
    if not launcher.exists():
        raise SystemExit(f"Missing launcher script: {launcher}")
    data = load_config()
    actions = [action for action in data.get("actions", []) if action.get("label") not in TIMELINE_LABELS]
    actions.append(
        {
            "enabled": True,
            "label": "Timeline: Open in Timeline Builder",
            "command": f"'{launcher}' {{path}}",
            "extensions": [".csv"],
            "mime_types": [],
            "selection": "single",
            "include_dirs": False,
            "terminal": False,
            "description": "Open the selected Jira CSV in the Timeline Builder GUI.",
        }
    )
    data["actions"] = actions
    backup = save_config(data)
    print(f"Installed optional Nautilus action: Timeline: Open in Timeline Builder")
    print(f"Command target: {launcher}")
    print(f"Config: {CONFIG_PATH}")
    if backup:
        print(f"Backup: {backup}")
    print("Restart Nautilus to refresh the menu: nautilus -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
