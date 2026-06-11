"""One user-facing CLI for Timeline Builder."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .ai_patch import apply_patch, load_json
from .csv_loader import write_numbered_csv
from .draft_builder import prepare
from .drawio_desktop import open_path, status_text
from .drawio_renderer import render, render_svg
from .naming import base_from_draft_path, base_from_reviewed_path, csv_artifact_paths, default_drawio_path, default_svg_path, paths_from_base
from .quality_gates import load_optional_review_packet, run_quality_gates, write_quality_report
from .review_packet import copy_prompt_text
from .validation import validate_patch, validate_render_preflight, validate_timeline


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_prepare(args: argparse.Namespace) -> int:
    paths = csv_artifact_paths(args.input_csv, args.output_folder)
    draft, packet, warnings = prepare(
        args.input_csv,
        unit_id=args.unit_id,
        source_file=args.source_file,
        draft_timeline_file=str(paths.draft.name),
        review_threshold=args.review_threshold,
        max_comment_chars=args.max_comment_chars,
    )
    write_json(paths.draft, draft)
    write_json(paths.review_packet, packet)
    write_json(paths.warnings, warnings)
    paths.ai_prompt.parent.mkdir(parents=True, exist_ok=True)
    paths.ai_prompt.write_text(
        copy_prompt_text(draft_path=paths.draft, packet_path=paths.review_packet, patch_path=paths.ai_patch),
        encoding="utf-8",
    )
    print(f"Artifact folder:        {paths.artifact_folder}")
    print(f"AI review folder:       {paths.ai_review_folder}")
    print(f"Wrote draft timeline JSON: {paths.draft}")
    print(f"Wrote AI review packet:  {paths.review_packet}")
    print(f"Wrote AI prompt file:    {paths.ai_prompt}")
    print(f"Wrote warnings JSON:    {paths.warnings}")
    print(f"Draft events: {len(draft['events'])}")
    print(f"Review items: {len(packet['review_items'])}")
    print(f"Warnings: {len(warnings)}")
    if args.write_numbered_csv:
        count = write_numbered_csv(args.input_csv, paths.numbered_csv)
        print(f"Wrote numbered CSV:     {paths.numbered_csv} ({count} rows)")
    return 0


def cmd_apply_review(args: argparse.Namespace) -> int:
    draft = load_json(args.draft_json)
    patch = load_json(args.ai_patch_json)
    base = base_from_draft_path(args.draft_json)
    paths = paths_from_base(base)
    reviewed_path = args.output or paths.reviewed
    quality_path = args.quality_report or paths.quality_report
    review_packet_path = args.review_packet or paths.review_packet
    review_packet = load_optional_review_packet(review_packet_path)
    patch_errors = validate_patch(patch, draft, review_packet=review_packet)

    if patch_errors:
        report = {
            "status": "blocked",
            "blockers": ["AI patch invalid"],
            "validation_errors": patch_errors,
        }
        write_quality_report(report, quality_path)
        print("AI patch is invalid:")
        for error in patch_errors:
            print(f"- {error}")
        print(f"Wrote quality report: {quality_path}")
        return 1

    reviewed = apply_patch(draft, patch, review_packet=review_packet)
    write_json(reviewed_path, reviewed)
    report = run_quality_gates(reviewed, review_packet=review_packet, max_unresolved_warnings=args.max_unresolved_warnings)
    write_quality_report(report, quality_path)

    print(f"Wrote reviewed timeline JSON: {reviewed_path}")
    print(f"Wrote quality report:        {quality_path}")
    print(f"Quality status: {report['status']}")
    for blocker in report.get("blockers", []):
        print(f"BLOCKER: {blocker}")
    return 1 if report.get("status") == "blocked" and not args.allow_blocked else 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = load_json(args.timeline_json)
    errors = validate_timeline(data)
    if args.render_preflight:
        errors.extend(error for error in validate_render_preflight(data) if error not in errors)
    if errors:
        print("Timeline JSON is invalid:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Timeline JSON is valid.")
    return 0


def _load_quality_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else None


def cmd_render(args: argparse.Namespace) -> int:
    reviewed_json = args.reviewed_json
    output = args.output or default_drawio_path(reviewed_json)
    base = base_from_reviewed_path(reviewed_json)
    quality_report_path = args.quality_report or paths_from_base(base).quality_report
    report = _load_quality_report(quality_report_path)
    if report and report.get("status") == "blocked" and not args.force_render:
        print(f"Render blocked by quality report: {quality_report_path}")
        for blocker in report.get("blockers", []):
            print(f"- {blocker}")
        print("Use --force-render only when you intentionally accept these blockers.")
        return 1
    render(reviewed_json, output)
    print(f"Wrote {output}")
    return 0


def cmd_export_svg(args: argparse.Namespace) -> int:
    output = args.output or default_svg_path(args.reviewed_json)
    render_svg(args.reviewed_json, output)
    print(f"Wrote {output}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    cmd_prepare(args)
    if args.ai:
        print("Automatic AI API mode is reserved for a future implementation. Manual AI patch review is required in this version.")
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    proc = open_path(args.path)
    if not proc:
        print(status_text())
        return 1
    print(f"Opened {args.path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Timeline Builder: Jira CSV -> draft -> AI patch -> reviewed timeline -> draw.io")
    parser.add_argument("--version", action="version", version=f"timeline-builder {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare", help="Create draft timeline JSON, AI review packet, and warnings from a Jira CSV.")
    prep.add_argument("input_csv", type=Path)
    prep.add_argument("--output-folder", type=Path, default=None)
    prep.add_argument("--unit-id", default=None)
    prep.add_argument("--source-file", default=None)
    prep.add_argument("--review-threshold", type=float, default=0.85)
    prep.add_argument("--max-comment-chars", type=int, default=1200)
    prep.add_argument("--write-numbered-csv", action="store_true", help="Debug/compatibility export only; not required for normal workflow.")
    prep.set_defaults(func=cmd_prepare)

    apply = sub.add_parser("apply-review", help="Apply AI patch JSON to a draft timeline and run quality gates.")
    apply.add_argument("draft_json", type=Path)
    apply.add_argument("ai_patch_json", type=Path)
    apply.add_argument("--review-packet", type=Path, default=None)
    apply.add_argument("--output", type=Path, default=None)
    apply.add_argument("--quality-report", type=Path, default=None)
    apply.add_argument("--max-unresolved-warnings", type=int, default=None)
    apply.add_argument("--allow-blocked", action="store_true", help="Return success even if quality gates block rendering.")
    apply.set_defaults(func=cmd_apply_review)

    validate = sub.add_parser("validate", help="Validate timeline JSON.")
    validate.add_argument("timeline_json", type=Path)
    validate.add_argument("--render-preflight", action="store_true")
    validate.set_defaults(func=cmd_validate)

    render_p = sub.add_parser("render", help="Render reviewed timeline JSON to editable draw.io.")
    render_p.add_argument("reviewed_json", type=Path)
    render_p.add_argument("output", type=Path, nargs="?")
    render_p.add_argument("--quality-report", type=Path, default=None)
    render_p.add_argument("--force-render", action="store_true")
    render_p.set_defaults(func=cmd_render)

    svg = sub.add_parser("export-svg", help="Export a simple SVG preview from reviewed timeline JSON.")
    svg.add_argument("reviewed_json", type=Path)
    svg.add_argument("output", type=Path, nargs="?")
    svg.set_defaults(func=cmd_export_svg)

    gen = sub.add_parser("generate", help="Prepare artifacts from CSV; --ai is reserved for future API mode.")
    gen.add_argument("input_csv", type=Path)
    gen.add_argument("--output-folder", type=Path, default=None)
    gen.add_argument("--unit-id", default=None)
    gen.add_argument("--source-file", default=None)
    gen.add_argument("--review-threshold", type=float, default=0.85)
    gen.add_argument("--max-comment-chars", type=int, default=1200)
    gen.add_argument("--write-numbered-csv", action="store_true")
    gen.add_argument("--ai", action="store_true")
    gen.set_defaults(func=cmd_generate)

    open_p = sub.add_parser("open", help="Open a draw.io file or other output path.")
    open_p.add_argument("path", type=Path)
    open_p.set_defaults(func=cmd_open)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
