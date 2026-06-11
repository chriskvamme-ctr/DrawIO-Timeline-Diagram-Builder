"""Quality gates that run before final render."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .review_packet import count_non_incident_review_items
from .validation import validate_render_preflight, validate_timeline


def run_quality_gates(
    timeline: dict[str, Any],
    *,
    review_packet: dict[str, Any] | None = None,
    max_unresolved_warnings: int | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    validation_errors = validate_timeline(timeline)
    if validation_errors:
        blockers.append("reviewed JSON invalid")

    render_errors = validate_render_preflight(timeline)
    for error in render_errors:
        if error == "zero renderable events":
            blockers.append("zero renderable events")
        elif error not in validation_errors:
            warnings.append(error)

    events = [event for event in timeline.get("events", []) if isinstance(event, dict)]
    lane_counts: dict[str, int] = {}
    for event in events:
        lane = str(event.get("lane"))
        lane_counts[lane] = lane_counts.get(lane, 0) + 1

    if len(events) >= 5 and lane_counts.get("incident", 0) == len(events):
        blockers.append(
            "Blocked: reviewed timeline contains only incident events. This usually means actions/context were not recovered from comments or non-Incident rows. Review packet must be checked before rendering."
        )

    patch_blockers = timeline.get("metadata", {}).get("blockers", []) if isinstance(timeline.get("metadata"), dict) else []
    if patch_blockers:
        blockers.append("AI patch reported blockers")

    non_incident_count = count_non_incident_review_items(review_packet)
    debug_report = timeline.get("metadata", {}).get("ai_patch_debug_report", {}) if isinstance(timeline.get("metadata"), dict) else {}
    if non_incident_count:
        seen = debug_report.get("non_incident_rows_seen") if isinstance(debug_report, dict) else None
        if seen in (None, 0, "0", []):
            blockers.append("non-Incident rows existed but were not confirmed reviewed in the AI patch debug_report")

    unresolved = [warning for warning in timeline.get("warnings", []) if isinstance(warning, dict) and warning.get("action") == "needs_review"]
    if max_unresolved_warnings is not None and len(unresolved) > max_unresolved_warnings:
        blockers.append(f"too many unresolved warnings: {len(unresolved)} > {max_unresolved_warnings}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "warnings": warnings,
        "metrics": {
            "event_count": len(events),
            "lane_counts": lane_counts,
            "warning_count": len(timeline.get("warnings", [])) if isinstance(timeline.get("warnings"), list) else 0,
            "unresolved_warning_count": len(unresolved),
            "non_incident_review_items": non_incident_count,
        },
        "validation_errors": validation_errors,
    }
    return report


def write_quality_report(report: dict[str, Any], path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_optional_review_packet(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    path = Path(path)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else None
