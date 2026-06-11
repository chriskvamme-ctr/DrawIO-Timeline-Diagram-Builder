"""Conservative Python draft timeline builder."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import ALLOWED_REVIEW_ACTIONS, DEFAULT_REVIEW_THRESHOLD, LANES
from .csv_loader import (
    Comment,
    JiraCsv,
    JiraRow,
    compact,
    load_jira_csv,
    row_date,
    row_review_context,
    shorten,
    source_fields_for,
)

# Conservative patterns. Anything unclear goes to the review packet.
REPLACEMENT_PATTERNS = [
    r"\breplaced\b",
    r"\breplacement\b",
    r"\bswapped\b",
    r"\bswap\b",
    r"\binstalled\b",
    r"\bexchanged\b",
    r"\brma\b",
    r"\bremoved\s+and\s+reinstalled\b",
    r"\breinstalled\b",
    r"\bchanged\s+(?:part|component)\b",
]

OTHER_ACTION_PATTERNS = [
    r"\bretested\b",
    r"\btested\b",
    r"\binspected\b",
    r"\bcleaned\b",
    r"\bconfigured\b",
    r"\bupdated\s+firmware\b",
    r"\bfirmware\s+updated\b",
    r"\bcollected\s+logs?\b",
    r"\bpulled\s+logs?\b",
    r"\bescalated\b",
    r"\bcreated\s+follow-up\s+issue\b",
    r"\brouted\s+to\s+team\b",
    r"\btriaged\b",
]

REVIEW_HINT_PATTERNS = [
    r"\bmaybe\b",
    r"\bpossibly\b",
    r"\bprobably\b",
    r"\bpossible\b",
    r"\bappears?\b",
    r"\blooks like\b",
    r"\bnot sure\b",
    r"\bunclear\b",
    r"\brecently\b",
    r"\bshould intake\b",
    r"\bcheck with team\b",
    r"\bmaybe bad part\b",
]

NOISE_PATTERNS = [
    r"^\s*https?://\S+\s*$",
    r"^\s*s3://\S+\s*$",
    r"^\s*(?:attachment|screenshot|video|clip)\b.*https?://\S+\s*$",
    r"\btriage_logs_pull\b",
    r"\bsync(?:ed|ing)?\b",
]

COMPONENT_HINTS = [
    "left arm",
    "right arm",
    "left leg",
    "right leg",
    "arm",
    "leg",
    "finger",
    "gripper",
    "motor",
    "encoder cable",
    "encoder",
    "cable",
    "battery",
    "board",
    "backplane",
    "sensor",
    "psu",
    "power supply",
    "conrod",
    "connector",
    "camera",
    "lidar",
    "wheel",
    "module",
]


def contains_any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def is_noise(text: str) -> bool:
    actionish = REPLACEMENT_PATTERNS + OTHER_ACTION_PATTERNS + REVIEW_HINT_PATTERNS
    return contains_any(NOISE_PATTERNS, text) and not contains_any(actionish, text)


def is_incident_type(value: str) -> bool:
    return value.strip().lower() == "incident"


def find_component(text: str) -> str | None:
    lower = text.lower()
    for hint in COMPONENT_HINTS:
        if hint in lower:
            return " ".join(word.capitalize() for word in hint.split())
    return None


def issue_title(row: JiraRow) -> str:
    key = row.value("issue_key")
    summary = row.value("summary")
    if key and summary:
        return shorten(f"{key} - {summary}", 90)
    return shorten(summary or key or "Untitled incident", 90)


def incident_details(row: JiraRow) -> str:
    parts: list[str] = []
    if row.value("status"):
        parts.append(f"Status: {row.value('status')}")
    if row.value("assignee"):
        parts.append(f"Assignee: {row.value('assignee')}")
    if row.value("resolved"):
        parts.append(f"Resolved: {row.value('resolved')}")
    return shorten("; ".join(parts), 220)


def source_datetime(value: str | None) -> str | None:
    """Extract a human-readable source timestamp without author/account noise."""
    text = compact(value)
    if not text:
        return None
    match = re.search(r"\b(\d{1,2}/[A-Za-z]{3}/\d{2,4})\s+(\d{1,2}:\d{2})(?:\s*([AP]M))?\b", text, re.IGNORECASE)
    if match:
        suffix = f" {match.group(3).upper()}" if match.group(3) else ""
        return f"{match.group(1)} {match.group(2)}{suffix}"
    match = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2})[T\s]+(\d{1,2}:\d{2})", text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    match = re.search(r"\b(\d{1,2}/[A-Za-z]{3}/\d{2,4})\b", text)
    if match:
        return match.group(1)
    return None


def clear_action(comment: Comment) -> dict[str, Any] | None:
    """Return a draft event for only obvious action comments."""
    text = comment.text
    if is_noise(text):
        return None
    if contains_any(REVIEW_HINT_PATTERNS, text):
        return None

    replacement = contains_any(REPLACEMENT_PATTERNS, text)
    other = contains_any(OTHER_ACTION_PATTERNS, text)
    if not replacement and not other:
        return None

    component = find_component(text)
    if replacement:
        # Component replacement events should only be created when the part/component is clear.
        if not component:
            return None
        lower = text.lower()
        if "install" in lower:
            title = f"Installed {component}"
        elif "swap" in lower:
            title = f"Swapped {component}"
        elif "rma" in lower:
            title = f"RMA for {component}"
        elif "exchang" in lower:
            title = f"Exchanged {component}"
        else:
            title = f"Replaced {component}"
        return {
            "lane": "component_replacement",
            "title": shorten(title, 90),
            "details": shorten(text, 220),
            "component": component,
            "confidence": 0.86,
            "inferred": False,
        }

    title_map = [
        (r"\bupdated\s+firmware\b|\bfirmware\s+updated\b", "Updated firmware"),
        (r"\bcollected\s+logs?\b|\bpulled\s+logs?\b", "Collected logs"),
        (r"\bretested\b", "Retested unit"),
        (r"\btested\b", "Tested unit"),
        (r"\binspected\b", "Inspected unit"),
        (r"\bcleaned\b", "Cleaned component"),
        (r"\bconfigured\b", "Configured unit"),
        (r"\bescalated\b", "Escalated issue"),
        (r"\btriaged\b", "Triaged issue"),
        (r"\brouted\s+to\s+team\b", "Routed to team"),
    ]
    title = "Action noted"
    for pattern, candidate in title_map:
        if re.search(pattern, text, re.IGNORECASE):
            title = candidate
            break
    return {
        "lane": "other",
        "title": title,
        "details": shorten(text, 220),
        "component": component,
        "confidence": 0.82,
        "inferred": False,
    }


def _review_item(
    review_id: str,
    *,
    reason: str,
    row: JiraRow,
    python_suggestion: str,
    allowed_actions: list[str] | None = None,
    comment: Comment | None = None,
    max_comment_chars: int = 1200,
) -> dict[str, Any]:
    context = row_review_context(row, max_comment_chars=max_comment_chars)
    comments = context.pop("comments")
    if comment is not None:
        comments = [
            {
                "field": comment.field,
                "date": comment.date,
                "text": shorten(comment.text, max_comment_chars),
            }
        ]
    return {
        "review_id": review_id,
        "reason": reason,
        "source_row": row.source_row,
        "issue_key": context["issue_key"],
        "issue_type": context["issue_type"],
        "summary": context["summary"],
        "created": context["created"],
        "resolved": context["resolved"],
        "status": context["status"],
        "assignee": context["assignee"],
        "priority": context["priority"],
        "labels": context["labels"],
        "description": context["description"],
        "comments": comments,
        "python_suggestion": python_suggestion,
        "allowed_actions": allowed_actions or list(ALLOWED_REVIEW_ACTIONS),
    }


def _new_review_id(counter: int) -> str:
    return f"R{counter:04d}"


def _new_event_id(counter: int) -> str:
    return f"E{counter:04d}"


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lane_rank = {"incident": 0, "component_replacement": 2, "other": 3}
    return sorted(events, key=lambda event: (event["date"], lane_rank.get(event["lane"], 9), event.get("issue_key") or "", event["event_id"]))


def _date_range(events: list[dict[str, Any]]) -> dict[str, str]:
    dates = [event["date"] for event in events if event.get("date")]
    if dates:
        return {"start": min(dates), "end": max(dates)}
    today = date.today().isoformat()
    return {"start": today, "end": today}


def prepare_from_loaded_csv(
    csv_data: JiraCsv,
    *,
    unit_id: str | None = None,
    source_file: str | None = None,
    draft_timeline_file: str | None = None,
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
    max_comment_chars: int = 1200,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    event_counter = 1
    review_counter = 1
    incident_rows = 0
    non_incident_rows = 0

    for row in csv_data.rows:
        rdate = row_date(row)
        itype = row.value("issue_type")

        if not rdate:
            review_items.append(
                _review_item(
                    _new_review_id(review_counter),
                    reason="Row has no usable Created or Resolved date.",
                    row=row,
                    python_suggestion="Keep unresolved unless the packet comments contain a clear date-supported event.",
                    allowed_actions=["create event", "keep warning", "mark needs human review"],
                    max_comment_chars=max_comment_chars,
                )
            )
            review_counter += 1
            warnings.append({"source_row": row.source_row, "reason": "Row has no usable Created or Resolved date.", "action": "needs_review"})
            continue

        if is_incident_type(itype) or (not csv_data.columns.issue_type and (row.value("issue_key") or row.value("summary"))):
            incident_rows += 1
            events.append(
                {
                    "event_id": _new_event_id(event_counter),
                    "lane": "incident",
                    "date": rdate,
                    "end_date": None,
                    "title": issue_title(row),
                    "details": incident_details(row),
                    "source_datetime": source_datetime(row.value("created")) or source_datetime(row.value("resolved")) or rdate,
                    "issue_key": row.value("issue_key") or None,
                    "component": None,
                    "source_rows": [row.source_row],
                    "source_fields": source_fields_for(csv_data.columns, "issue_type", "issue_key", "summary", "created", "status"),
                    "confidence": 0.97,
                    "inferred": False,
                }
            )
            event_counter += 1
        else:
            non_incident_rows += 1
            review_items.append(
                _review_item(
                    _new_review_id(review_counter),
                    reason=f"Non-Incident Jira row requires AI review: {itype or '(missing Issue Type)'}.",
                    row=row,
                    python_suggestion="Review this full row. Create a component_replacement or other event only if the source fields/comments clearly support it; otherwise keep a warning or mark human review.",
                    allowed_actions=["create event", "keep warning", "mark needs human review"],
                    max_comment_chars=max_comment_chars,
                )
            )
            review_counter += 1
            warnings.append({"source_row": row.source_row, "reason": f"Non-Incident Issue Type requires review: {itype or '(missing)'}", "action": "needs_review"})

        for comment in row.comments:
            if is_noise(comment.text):
                continue
            action = clear_action(comment)
            if action:
                events.append(
                    {
                        "event_id": _new_event_id(event_counter),
                        "lane": action["lane"],
                        "date": comment.date or rdate,
                        "end_date": None,
                        "title": action["title"],
                        "details": action["details"],
                        "source_datetime": source_datetime(comment.text) or comment.date or rdate,
                        "issue_key": row.value("issue_key") or None,
                        "component": action["component"],
                        "source_rows": [row.source_row],
                        "source_fields": [comment.field],
                        "confidence": action["confidence"],
                        "inferred": action["inferred"],
                    }
                )
                event_counter += 1
            elif contains_any(REPLACEMENT_PATTERNS + OTHER_ACTION_PATTERNS + REVIEW_HINT_PATTERNS, comment.text):
                review_items.append(
                    _review_item(
                        _new_review_id(review_counter),
                        reason="Comment has possible timeline/action meaning but was not rendered by conservative rules.",
                        row=row,
                        comment=comment,
                        python_suggestion="Resolve only if the comment clearly supports a dated event. Otherwise keep unresolved.",
                        allowed_actions=["create event", "keep warning", "mark needs human review"],
                        max_comment_chars=max_comment_chars,
                    )
                )
                review_counter += 1
                warnings.append({"source_row": row.source_row, "reason": f"Possible timeline/action comment needs AI review. Field: {comment.field}", "action": "needs_review"})

    events = _sort_events(events)
    low_confidence_events = [event for event in events if float(event.get("confidence", 1)) < review_threshold]

    draft = {
        "unit_id": unit_id or csv_data.path.stem,
        "source_file": source_file or csv_data.path.name,
        "date_range": _date_range(events),
        "lanes": LANES,
        "events": events,
        "warnings": warnings,
        "metadata": {
            "pipeline": "python_draft_pending_ai_patch",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "review_threshold": review_threshold,
            "source_rows_generated": csv_data.source_rows_generated,
            "input_rows": len(csv_data.rows),
            "incident_rows": incident_rows,
            "non_incident_rows": non_incident_rows,
        },
    }

    review_packet = {
        "packet_type": "timeline_ai_review_packet",
        "source_file": source_file or csv_data.path.name,
        "draft_timeline_file": draft_timeline_file,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_threshold": review_threshold,
        "draft_summary": {
            "input_rows": len(csv_data.rows),
            "incident_rows": incident_rows,
            "non_incident_rows": non_incident_rows,
            "draft_events": len(events),
            "low_confidence_events": len(low_confidence_events),
            "warnings": len(warnings),
            "review_items": len(review_items),
            "source_rows_generated": csv_data.source_rows_generated,
            "columns_detected": csv_data.columns.as_dict(),
        },
        "review_items": review_items,
        "low_confidence_events": low_confidence_events,
        "warnings": warnings,
        "instructions_summary": (
            "Python prepared a conservative draft. AI must return patch JSON only, not a full timeline replacement. "
            "Create/edit/remove events only when source rows clearly support the change. Every new event must include source_rows and source_fields. "
            "Keep unresolved warnings or mark human review when evidence is insufficient."
        ),
    }
    return draft, review_packet, warnings


def prepare(
    input_csv: Path,
    *,
    unit_id: str | None = None,
    source_file: str | None = None,
    draft_timeline_file: str | None = None,
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
    max_comment_chars: int = 1200,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    csv_data = load_jira_csv(input_csv)
    return prepare_from_loaded_csv(
        csv_data,
        unit_id=unit_id,
        source_file=source_file,
        draft_timeline_file=draft_timeline_file,
        review_threshold=review_threshold,
        max_comment_chars=max_comment_chars,
    )
