"""Detect and open draw.io Desktop when available."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


DETECTION_ORDER = [
    ["drawio"],
    ["draw.io"],
    ["diagrams.net"],
    ["flatpak", "run", "com.jgraph.drawio.desktop"],
    ["xdg-open"],
]


def detect_drawio_command() -> list[str] | None:
    for command in DETECTION_ORDER:
        executable = command[0]
        if executable == "flatpak":
            if shutil.which("flatpak"):
                return command
        elif shutil.which(executable):
            return command
    return None


def open_path(path: Path) -> subprocess.Popen[str] | None:
    command = detect_drawio_command()
    if not command:
        return None
    return subprocess.Popen([*command, str(Path(path))], text=True)


def status_text() -> str:
    command = detect_drawio_command()
    if not command:
        return "draw.io Desktop not found; xdg-open fallback unavailable."
    if command[0] == "xdg-open":
        return "draw.io Desktop not found; will use xdg-open fallback."
    return "Found draw.io command: " + " ".join(command)
