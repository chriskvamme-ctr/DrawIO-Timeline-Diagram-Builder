"""AI patch validation and application."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import LANES
from .validation import validate_patch, validate_timeline


def load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def recompute_date_range(data: dict[str, Any]) -> None:
    dates = [event.get("date") for event in data.get("events", []) if isinstance(event, dict) and event.get("date")]
    if dates:
        data["date_range"] = {"start": min(dates), "end": max(dates)}


def sort_events(data: dict[str, Any]) -> None:
    lane_rank = {"incident": 0, "component_replacement": 2, "other": 3}
    data["events"] = sorted(
        data.get("events", []),
        key=lambda event: (event.get("date") or "9999-99-99", lane_rank.get(event.get("lane"), 9), event.get("issue_key") or "", event.get("event_id") or ""),
    )




def _row_issue_keys(draft: dict[str, Any], review_packet: dict[str, Any] | None) -> dict[int, set[str]]:
    rows: dict[int, set[str]] = {}

    def add(row: Any, issue_key: Any) -> None:
        if not isinstance(row, int):
            return
        key = str(issue_key or "").strip()
        if key and key.lower() not in {"none", "null", "n/a"}:
            rows.setdefault(row, set()).add(key)

    for event in draft.get("events", []):
        if not isinstance(event, dict):
            continue
        for row in event.get("source_rows", []):
            add(row, event.get("issue_key"))

    if isinstance(review_packet, dict):
        for item in review_packet.get("review_items", []):
            if isinstance(item, dict):
                add(item.get("source_row"), item.get("issue_key"))
        for event in review_packet.get("low_confidence_events", []):
            if not isinstance(event, dict):
                continue
            for row in event.get("source_rows", []):
                add(row, event.get("issue_key"))

    return rows


def _fill_missing_issue_key(event: dict[str, Any], row_issue_keys: dict[int, set[str]]) -> None:
    if str(event.get("issue_key") or "").strip():
        return
    possible: set[str] = set()
    for row in event.get("source_rows", []):
        if isinstance(row, int):
            possible.update(row_issue_keys.get(row, set()))
    if len(possible) == 1:
        event["issue_key"] = next(iter(possible))


def apply_patch(draft: dict[str, Any], patch: dict[str, Any], review_packet: dict[str, Any] | None = None) -> dict[str, Any]:
    errors = validate_patch(patch, draft, review_packet=review_packet)
    if errors:
        raise ValueError("AI patch is invalid:\n" + "\n".join(f"- {error}" for error in errors))

    reviewed = copy.deepcopy(draft)
    events_by_id = {event["event_id"]: event for event in reviewed.get("events", [])}

    for edit in patch.get("event_edits", []):
        event = events_by_id[edit["event_id"]]
        for field, value in edit.get("changes", {}).items():
            event[field] = value

    removal_ids = {removal["event_id"] for removal in patch.get("event_removals", [])}
    if removal_ids:
        reviewed["events"] = [event for event in reviewed.get("events", []) if event.get("event_id") not in removal_ids]

    existing_ids = {event.get("event_id") for event in reviewed.get("events", [])}
    row_issue_keys = _row_issue_keys(draft, review_packet)
    for new_event in patch.get("new_events", []):
        if new_event["event_id"] in existing_ids:
            raise ValueError(f"Duplicate new event id after removals: {new_event['event_id']}")
        event_copy = copy.deepcopy(new_event)
        _fill_missing_issue_key(event_copy, row_issue_keys)
        reviewed.setdefault("events", []).append(event_copy)
        existing_ids.add(event_copy["event_id"])

    # Keep original warnings, plus explicit human-review/blocker warnings from the patch.
    for item in patch.get("human_review_needed", []):
        warning = _warning_from_patch_item(item, default_reason="AI marked item as needing human review")
        if warning:
            reviewed.setdefault("warnings", []).append(warning)
    for item in patch.get("blockers", []):
        warning = _warning_from_patch_item(item, default_reason="AI reported blocker")
        if warning:
            reviewed.setdefault("warnings", []).append(warning)

    reviewed["lanes"] = LANES
    reviewed["metadata"] = dict(reviewed.get("metadata", {}))
    reviewed["metadata"].update(
        {
            "pipeline": "reviewed_with_ai_patch",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "ai_patch_summary": patch.get("summary"),
            "ai_patch_debug_report": patch.get("debug_report"),
            "review_decisions": patch.get("review_decisions", []),
            "reviewed_source_rows": patch.get("reviewed_source_rows", []),
            "reviewed_review_ids": patch.get("reviewed_review_ids", []),
            "warnings_to_keep": patch.get("warnings_to_keep", []),
            "event_removals": patch.get("event_removals", []),
            "human_review_needed": patch.get("human_review_needed", []),
            "blockers": patch.get("blockers", []),
        }
    )
    sort_events(reviewed)
    recompute_date_range(reviewed)

    timeline_errors = validate_timeline(reviewed)
    if timeline_errors:
        raise ValueError("Reviewed timeline is invalid after applying patch:\n" + "\n".join(f"- {error}" for error in timeline_errors))
    return reviewed


def _warning_from_patch_item(item: Any, *, default_reason: str) -> dict[str, Any] | None:
    if isinstance(item, dict):
        source_row = item.get("source_row")
        source_rows = item.get("source_rows")
        if not isinstance(source_row, int) and isinstance(source_rows, list) and source_rows and isinstance(source_rows[0], int):
            source_row = source_rows[0]
        if not isinstance(source_row, int):
            return None
        reason = str(item.get("reason") or item.get("blocker") or default_reason)
        return {"source_row": source_row, "reason": reason, "action": "needs_review"}
    return None


def apply_patch_files(draft_path: Path, patch_path: Path, reviewed_path: Path, review_packet_path: Path | None = None) -> dict[str, Any]:
    draft = load_json(draft_path)
    patch = load_json(patch_path)
    review_packet = load_json(review_packet_path) if review_packet_path else None
    reviewed = apply_patch(draft, patch, review_packet=review_packet)
    Path(reviewed_path).parent.mkdir(parents=True, exist_ok=True)
    Path(reviewed_path).write_text(json.dumps(reviewed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return reviewed
