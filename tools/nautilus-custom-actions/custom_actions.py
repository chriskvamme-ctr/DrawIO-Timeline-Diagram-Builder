#!/usr/bin/env python3
"""
Nautilus Custom Actions
A small configurable Nautilus/GNOME Files context-menu extension.

Config: ~/.config/nautilus-custom-actions/actions.json
Settings editor: nca-settings
"""
from __future__ import annotations

import fnmatch
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import gi

try:
    gi.require_version("Nautilus", "4.0")
except (ValueError, ImportError):
    # Some older Ubuntu/GNOME combinations expose Nautilus without this call.
    pass

from gi.repository import GObject, Nautilus  # noqa: E402

APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "nautilus-custom-actions"
CONFIG_PATH = APP_DIR / "actions.json"

DEFAULT_CONFIG: Dict[str, Any] = {"actions": []}


def _ensure_config_exists() -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    except Exception:
        # Nautilus should not crash because config creation failed.
        pass


def _load_config() -> Dict[str, Any]:
    _ensure_config_exists()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return DEFAULT_CONFIG
        if not isinstance(data.get("actions"), list):
            data["actions"] = []
        return data
    except Exception:
        return DEFAULT_CONFIG


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_ext(ext: str) -> str:
    ext = ext.strip().lower()
    if not ext:
        return ""
    if ext.startswith("*"):
        return ext
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def _shell_quote(value: Optional[str]) -> str:
    return shlex.quote(value or "")


def _safe_get_file_info(file_info: Nautilus.FileInfo) -> Dict[str, Any]:
    location = None
    try:
        location = file_info.get_location()
    except Exception:
        location = None

    path = None
    uri = ""
    if location is not None:
        try:
            path = location.get_path()
        except Exception:
            path = None
        try:
            uri = location.get_uri() or ""
        except Exception:
            uri = ""

    if not uri:
        try:
            uri = file_info.get_uri() or ""
        except Exception:
            uri = ""

    try:
        name = file_info.get_name() or ""
    except Exception:
        name = Path(path).name if path else ""

    try:
        mime = file_info.get_mime_type() or ""
    except Exception:
        mime = ""

    try:
        is_dir = bool(file_info.is_directory())
    except Exception:
        is_dir = bool(path and Path(path).is_dir()) or mime == "inode/directory"

    return {
        "path": path,
        "uri": uri,
        "name": name,
        "mime": mime,
        "is_dir": is_dir,
    }


def _matches_action(action: Dict[str, Any], infos: List[Dict[str, Any]]) -> bool:
    if not action.get("enabled", True):
        return False
    if not str(action.get("label", "")).strip():
        return False
    if not str(action.get("command", "")).strip():
        return False
    if not infos:
        return False

    selection = str(action.get("selection", "single")).strip().lower()
    if selection == "single" and len(infos) != 1:
        return False
    if selection == "multiple" and len(infos) < 2:
        return False
    if selection not in {"single", "multiple", "any"}:
        # Bad config should fail safely.
        return False

    include_dirs = bool(action.get("include_dirs", False))
    if any(info["is_dir"] for info in infos) and not include_dirs:
        return False

    allow_remote = bool(action.get("allow_remote", False))
    if any(not info.get("path") for info in infos) and not allow_remote:
        return False

    extensions = [_normalize_ext(ext) for ext in _as_list(action.get("extensions"))]
    extensions = [ext for ext in extensions if ext]
    mime_types = [mime.lower() for mime in _as_list(action.get("mime_types"))]

    # Empty extensions and empty MIME types means "show for any selected item".
    if not extensions and not mime_types:
        return True

    for info in infos:
        name = str(info.get("name") or "").lower()
        path = str(info.get("path") or "").lower()
        suffix = Path(path or name).suffix.lower()
        mime = str(info.get("mime") or "").lower()

        ext_ok = False
        for ext in extensions:
            if ext.startswith("*"):
                ext_ok = fnmatch.fnmatch(name, ext) or fnmatch.fnmatch(path, ext)
            else:
                ext_ok = suffix == ext
            if ext_ok:
                break

        mime_ok = any(fnmatch.fnmatch(mime, pattern) for pattern in mime_types)

        # If both filters are present, either one can match the item.
        if not (ext_ok or mime_ok):
            return False

    return True


def _render_command(command: str, infos: List[Dict[str, Any]]) -> str:
    paths = [info["path"] for info in infos if info.get("path")]
    uris = [info["uri"] for info in infos if info.get("uri")]
    names = [info["name"] for info in infos if info.get("name")]
    first_path = paths[0] if paths else ""
    first_uri = uris[0] if uris else ""
    first_name = names[0] if names else ""
    first_dir = str(Path(first_path).parent) if first_path else ""

    replacements = {
        "{path}": _shell_quote(first_path),
        "{paths}": " ".join(_shell_quote(path) for path in paths),
        "{uri}": _shell_quote(first_uri),
        "{uris}": " ".join(_shell_quote(uri) for uri in uris),
        "{name}": _shell_quote(first_name),
        "{names}": " ".join(_shell_quote(name) for name in names),
        "{dir}": _shell_quote(first_dir),
        "{raw_path}": first_path,
        "{raw_paths}": "\n".join(paths),
    }

    rendered = command
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def _build_env(infos: List[Dict[str, Any]]) -> Dict[str, str]:
    env = os.environ.copy()
    paths = [info["path"] for info in infos if info.get("path")]
    uris = [info["uri"] for info in infos if info.get("uri")]
    names = [info["name"] for info in infos if info.get("name")]
    env.update(
        {
            "NCA_PATH": paths[0] if paths else "",
            "NCA_PATHS": "\n".join(paths),
            "NCA_URI": uris[0] if uris else "",
            "NCA_URIS": "\n".join(uris),
            "NCA_NAME": names[0] if names else "",
            "NCA_NAMES": "\n".join(names),
        }
    )
    return env


class NautilusCustomActions(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self) -> None:
        super().__init__()

    def menu_activate_cb(self, menu: Nautilus.MenuItem, action: Dict[str, Any], infos: List[Dict[str, Any]]) -> None:
        command = _render_command(str(action.get("command", "")), infos)
        if not command.strip():
            return

        paths = [info["path"] for info in infos if info.get("path")]
        cwd = str(Path(paths[0]).parent) if paths else str(Path.home())
        env = _build_env(infos)

        try:
            if bool(action.get("terminal", False)):
                # Use gnome-terminal when available, otherwise try the system terminal emulator.
                try:
                    subprocess.Popen(["gnome-terminal", "--", "bash", "-lc", command], cwd=cwd, env=env, start_new_session=True)
                except FileNotFoundError:
                    subprocess.Popen(["x-terminal-emulator", "-e", "bash", "-lc", command], cwd=cwd, env=env, start_new_session=True)
            else:
                subprocess.Popen(command, shell=True, cwd=cwd, env=env, start_new_session=True)
        except Exception as exc:
            # Avoid crashing Nautilus. Log where a developer can find it when starting nautilus from a terminal.
            print(f"nautilus-custom-actions: failed to run command: {exc}")

    def get_file_items(self, files: List[Nautilus.FileInfo]) -> List[Nautilus.MenuItem]:
        infos = [_safe_get_file_info(file_info) for file_info in files]
        config = _load_config()
        items: List[Nautilus.MenuItem] = []

        for index, action in enumerate(config.get("actions", [])):
            if not isinstance(action, dict):
                continue
            if not _matches_action(action, infos):
                continue

            label = str(action.get("label", "Custom Action"))
            description = str(action.get("description", ""))
            item = Nautilus.MenuItem(
                name=f"NautilusCustomActions::action_{index}",
                label=label,
                tip=description,
            )
            item.connect("activate", self.menu_activate_cb, action, infos)
            items.append(item)

        return items

    def get_background_items(self, current_folder: Nautilus.FileInfo) -> List[Nautilus.MenuItem]:
        # This project is focused on selected files/folders, not blank-area folder actions.
        return []
