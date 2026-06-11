#!/usr/bin/env python3
"""Compatibility wrapper for the old no-AI normalizer.

This writes the Python draft timeline to the requested output path. The intended
workflow is now `scripts/timeline_builder.py prepare`, manual AI patch review,
`apply-review`, then `render`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timeline_builder.draft_builder import prepare


def main() -> int:
    parser = argparse.ArgumentParser(description="Compatibility: create conservative draft timeline JSON from Jira CSV.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    draft, _packet, warnings = prepare(args.input_csv, draft_timeline_file=args.output_json.name)
    draft["warnings"] = warnings
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    warnings_path = args.output_json.with_name(args.output_json.stem + "_warnings.json")
    warnings_path.write_text(json.dumps(warnings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote conservative draft timeline JSON: {args.output_json}")
    print(f"Wrote warnings JSON: {warnings_path}")
    print("NOTE: Manual AI patch review is required for the intended final workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
