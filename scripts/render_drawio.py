#!/usr/bin/env python3
"""Compatibility wrapper for `scripts/timeline_builder.py render`."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timeline_builder.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["render", *sys.argv[1:]]))
