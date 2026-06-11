#!/usr/bin/env python3
"""Compatibility/debug helper for exporting source_row numbers.

The normal Timeline Builder workflow now handles source rows internally and does
not require this pre-step.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timeline_builder.csv_loader import write_numbered_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug/compatibility export: add source_row numbers to a Jira CSV.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--column-name", default="source_row")
    args = parser.parse_args()
    count = write_numbered_csv(args.input_csv, args.output_csv, args.column_name)
    print(f"Wrote {count} rows to {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
