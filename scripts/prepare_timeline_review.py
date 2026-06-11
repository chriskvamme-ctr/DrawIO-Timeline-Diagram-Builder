#!/usr/bin/env python3
"""Compatibility wrapper for `scripts/timeline_builder.py prepare`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from timeline_builder.cli import main as cli_main


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Jira CSV timeline draft and AI review packet.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output-prefix", type=Path, default=None, help="Compatibility option. Uses the prefix's parent as output folder.")
    parser.add_argument("--unit-id", default=None)
    parser.add_argument("--source-file", default=None)
    parser.add_argument("--max-comment-chars", type=int, default=1200)
    parser.add_argument("--review-threshold", type=float, default=0.85)
    parser.add_argument("--write-numbered-csv", action="store_true")
    args = parser.parse_args()

    argv = ["prepare", str(args.input_csv), "--max-comment-chars", str(args.max_comment_chars), "--review-threshold", str(args.review_threshold)]
    if args.output_prefix:
        argv += ["--output-folder", str(args.output_prefix.parent)]
        if args.output_prefix.name != args.input_csv.stem:
            print("WARNING: --output-prefix basename is ignored by the new fixed naming scheme; CSV basename is used.", file=sys.stderr)
    if args.unit_id:
        argv += ["--unit-id", args.unit_id]
    if args.source_file:
        argv += ["--source-file", args.source_file]
    if args.write_numbered_csv:
        argv.append("--write-numbered-csv")
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
