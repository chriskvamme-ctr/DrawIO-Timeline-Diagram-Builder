"""Shared timeline, patch, source-support, and render validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import EVENT_LANES, LANES, PATCH_ALLOWED_EDIT_FIELDS, PATCH_REQUIRED_KEYS, REVIEW_DECISION_ACTIONS, WARNING_ACTIONS
from .csv_loader import parse_date as parse_source_date

REQUIRED_ROOT_KEYS = {"unit_id", "source_file", "date_range", "lanes", "events", "warnings"}
REQUIRED_EVENT_KEYS = {
    "event_id",
    "lane",
    "date",
    "end_date",
    "title",
    "details",
    "issue_key",
    "component",
    "source_rows",
    "source_fields",
    "confidence",
    "inferred",
}


_MAX_CARD_TITLE_CHARS = 72
_MAX_CARD_DETAILS_CHARS = 160


def is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _event_errors(event: Any, idx: int, *, prefix: str = "events") -> list[str]:
    errors: list[str] = []
    if not isinstance(event, dict):
        return [f"{prefix}[{idx}] must be an object"]

    missing = REQUIRED_EVENT_KEYS - set(event)
    if missing:
        errors.append(f"{prefix}[{idx}] missing keys: {sorted(missing)}")

    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        errors.append(f"{prefix}[{idx}].event_id must be a non-empty string")

    lane = event.get("lane")
    if lane not in EVENT_LANES:
        errors.append(f"{prefix}[{idx}].lane must be one of {sorted(EVENT_LANES)}")

    if not is_iso_date(event.get("date")):
        errors.append(f"{prefix}[{idx}].date must be YYYY-MM-DD")

    end_date = event.get("end_date")
    if end_date is not None and not is_iso_date(end_date):
        errors.append(f"{prefix}[{idx}].end_date must be null or YYYY-MM-DD")

    if not isinstance(event.get("title"), str) or not event.get("title", "").strip():
        errors.append(f"{prefix}[{idx}].title must be a non-empty string")

    if not isinstance(event.get("details"), str):
        errors.append(f"{prefix}[{idx}].details must be a string")

    source_rows = event.get("source_rows")
    if not isinstance(source_rows, list) or not source_rows or not all(isinstance(x, int) for x in source_rows):
        errors.append(f"{prefix}[{idx}].source_rows must be a non-empty list of integers")

    source_fields = event.get("source_fields")
    if not isinstance(source_fields, list) or not source_fields or not all(isinstance(x, str) and x.strip() for x in source_fields):
        errors.append(f"{prefix}[{idx}].source_fields must be a non-empty list of strings")

    confidence = event.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append(f"{prefix}[{idx}].confidence must be a number from 0 to 1")

    if not isinstance(event.get("inferred"), bool):
        errors.append(f"{prefix}[{idx}].inferred must be true or false")

    return errors


def validate_timeline(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Timeline JSON root must be an object"]

    missing_root = REQUIRED_ROOT_KEYS - set(data)
    if missing_root:
        errors.append(f"Missing root keys: {sorted(missing_root)}")

    date_range = data.get("date_range", {})
    if not isinstance(date_range, dict):
        errors.append("date_range must be an object")
    else:
        if not is_iso_date(date_range.get("start")):
            errors.append("date_range.start must be YYYY-MM-DD")
        if not is_iso_date(date_range.get("end")):
            errors.append("date_range.end must be YYYY-MM-DD")
        if is_iso_date(date_range.get("start")) and is_iso_date(date_range.get("end")) and date_range["start"] > date_range["end"]:
            errors.append("date_range.start must be before or equal to date_range.end")

    if data.get("lanes") != LANES:
        errors.append("lanes must equal ['incident', 'date', 'component_replacement', 'other']")

    events = data.get("events")
    if not isinstance(events, list):
        errors.append("events must be a list")
        return errors

    seen_event_ids: set[str] = set()
    for idx, event in enumerate(events, start=1):
        errors.extend(_event_errors(event, idx))
        if isinstance(event, dict):
            event_id = event.get("event_id")
            if isinstance(event_id, str) and event_id.strip():
                if event_id in seen_event_ids:
                    errors.append(f"Duplicate event_id: {event_id}")
                seen_event_ids.add(event_id)

    warnings = data.get("warnings")
    if not isinstance(warnings, list):
        errors.append("warnings must be a list")
    else:
        for idx, warning in enumerate(warnings, start=1):
            if not isinstance(warning, dict):
                errors.append(f"warnings[{idx}] must be an object")
                continue
            if not isinstance(warning.get("source_row"), int):
                errors.append(f"warnings[{idx}].source_row must be an integer")
            if warning.get("action") not in WARNING_ACTIONS:
                errors.append(f"warnings[{idx}].action has invalid value")
            if not isinstance(warning.get("reason"), str) or not warning.get("reason", "").strip():
                errors.append(f"warnings[{idx}].reason must be a non-empty string")

    return errors


def validate_render_preflight(data: dict[str, Any]) -> list[str]:
    errors = validate_timeline(data)
    events = data.get("events") if isinstance(data, dict) else None
    if isinstance(events, list):
        if not events:
            errors.append("zero renderable events")
        for idx, event in enumerate(events, start=1):
            if isinstance(event, dict):
                if event.get("lane") not in EVENT_LANES:
                    errors.append(f"events[{idx}] has unsupported lane for render")
                if not is_iso_date(event.get("date")):
                    errors.append(f"events[{idx}] has no valid render date")
                if not str(event.get("title") or "").strip():
                    errors.append(f"events[{idx}] has no title")
    return errors


def _integer_list(value: Any) -> list[int] | None:
    if not isinstance(value, list) or not value or not all(isinstance(x, int) for x in value):
        return None
    return list(value)


def _field_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _field_missing(field: Any, supported_fields: set[str]) -> bool:
    return _field_key(field) not in {_field_key(supported) for supported in supported_fields}


def _event_rows(event: dict[str, Any]) -> set[int]:
    rows = event.get("source_rows")
    return set(rows) if isinstance(rows, list) and all(isinstance(x, int) for x in rows) else set()


def _draft_events_by_id(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        event.get("event_id"): event
        for event in draft.get("events", [])
        if isinstance(event, dict) and isinstance(event.get("event_id"), str)
    }


def _known_source_rows(draft: dict[str, Any], review_packet: dict[str, Any] | None) -> set[int]:
    rows: set[int] = set()
    for event in draft.get("events", []):
        if isinstance(event, dict):
            rows.update(_event_rows(event))
    for warning in draft.get("warnings", []):
        if isinstance(warning, dict) and isinstance(warning.get("source_row"), int):
            rows.add(warning["source_row"])
    if isinstance(review_packet, dict):
        for item in review_packet.get("review_items", []):
            if isinstance(item, dict) and isinstance(item.get("source_row"), int):
                rows.add(item["source_row"])
        for event in review_packet.get("low_confidence_events", []):
            if isinstance(event, dict):
                rows.update(_event_rows(event))
        for warning in review_packet.get("warnings", []):
            if isinstance(warning, dict) and isinstance(warning.get("source_row"), int):
                rows.add(warning["source_row"])
    return rows


def _source_support(draft: dict[str, Any], review_packet: dict[str, Any] | None) -> tuple[dict[int, set[str]], dict[int, set[str]]]:
    """Return supported dates and fields by source_row.

    This intentionally uses only dates/fields Python put into the draft/review packet.
    A new AI-created event date must come from one of these values when packet context
    is available; otherwise it is likely invented or unsupported.
    """
    dates_by_row: dict[int, set[str]] = {}
    fields_by_row: dict[int, set[str]] = {}

    def add(row: int, *, date_value: Any = None, field_values: Any = None) -> None:
        if not isinstance(row, int):
            return
        parsed = parse_source_date(date_value) if date_value else None
        if parsed:
            dates_by_row.setdefault(row, set()).add(parsed)
        if isinstance(field_values, list):
            for field in field_values:
                if isinstance(field, str) and field.strip():
                    fields_by_row.setdefault(row, set()).add(field.strip())
        elif isinstance(field_values, str) and field_values.strip():
            fields_by_row.setdefault(row, set()).add(field_values.strip())

    for event in draft.get("events", []):
        if not isinstance(event, dict):
            continue
        for row in _event_rows(event):
            add(row, date_value=event.get("date"), field_values=event.get("source_fields"))

    if isinstance(review_packet, dict):
        for item in review_packet.get("review_items", []):
            if not isinstance(item, dict):
                continue
            row = item.get("source_row")
            if not isinstance(row, int):
                continue
            # These field names match the packet concepts; comments carry original CSV comment fields.
            concept_fields = []
            for key in ["created", "resolved", "status", "assignee", "priority", "labels", "description", "summary", "issue_key", "issue_type"]:
                if item.get(key) not in (None, ""):
                    concept_fields.append(key)
            add(row, date_value=item.get("created"), field_values=concept_fields)
            add(row, date_value=item.get("resolved"), field_values=None)
            for comment in item.get("comments", []):
                if isinstance(comment, dict):
                    add(row, date_value=comment.get("date"), field_values=comment.get("field"))
        for event in review_packet.get("low_confidence_events", []):
            if isinstance(event, dict):
                for row in _event_rows(event):
                    add(row, date_value=event.get("date"), field_values=event.get("source_fields"))
    return dates_by_row, fields_by_row


def _review_items_by_id(review_packet: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(review_packet, dict):
        return {}
    return {
        item.get("review_id"): item
        for item in review_packet.get("review_items", [])
        if isinstance(item, dict) and isinstance(item.get("review_id"), str) and item.get("review_id")
    }


def _validate_review_decisions(patch: dict[str, Any], review_packet: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    decisions = patch.get("review_decisions")
    if not isinstance(decisions, list):
        return ["patch.review_decisions must be a list"]

    review_items = _review_items_by_id(review_packet)
    seen: set[str] = set()
    new_event_ids = {event.get("event_id") for event in patch.get("new_events", []) if isinstance(event, dict)}
    edited_ids = {edit.get("event_id") for edit in patch.get("event_edits", []) if isinstance(edit, dict)}
    removed_ids = {removal.get("event_id") for removal in patch.get("event_removals", []) if isinstance(removal, dict)}

    for idx, decision in enumerate(decisions, start=1):
        if not isinstance(decision, dict):
            errors.append(f"review_decisions[{idx}] must be an object")
            continue
        review_id = decision.get("review_id")
        if not isinstance(review_id, str) or not review_id.strip():
            errors.append(f"review_decisions[{idx}].review_id is required")
        elif review_id in seen:
            errors.append(f"review_decisions[{idx}].review_id is duplicated: {review_id}")
        else:
            seen.add(review_id)
        if review_items and review_id not in review_items:
            errors.append(f"review_decisions[{idx}].review_id does not exist in review packet: {review_id}")

        action = decision.get("action")
        if action not in REVIEW_DECISION_ACTIONS:
            errors.append(f"review_decisions[{idx}].action must be one of {sorted(REVIEW_DECISION_ACTIONS)}")
        if not isinstance(decision.get("reason"), str) or not decision.get("reason", "").strip():
            errors.append(f"review_decisions[{idx}].reason is required")
        rows = _integer_list(decision.get("source_rows"))
        if rows is None:
            errors.append(f"review_decisions[{idx}].source_rows must be a non-empty integer list")
        elif review_items and isinstance(review_id, str) and review_id in review_items:
            expected_row = review_items[review_id].get("source_row")
            if isinstance(expected_row, int) and expected_row not in rows:
                errors.append(f"review_decisions[{idx}].source_rows must include review item source_row {expected_row}")

        if action == "create_event" and decision.get("new_event_id") not in new_event_ids:
            errors.append(f"review_decisions[{idx}] action=create_event must reference new_event_id from patch.new_events")
        if action == "edit_event" and decision.get("event_id") not in edited_ids:
            errors.append(f"review_decisions[{idx}] action=edit_event must reference event_id from patch.event_edits")
        if action == "remove_event" and decision.get("event_id") not in removed_ids:
            errors.append(f"review_decisions[{idx}] action=remove_event must reference event_id from patch.event_removals")

    return errors



def _review_item_order(review_packet: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(review_packet, dict):
        return []
    return [item for item in review_packet.get("review_items", []) if isinstance(item, dict)]


def _add_covered_row(row: int, rows_to_review_ids: dict[int, set[str]], covered_ids: set[str]) -> None:
    for review_id in rows_to_review_ids.get(row, set()):
        covered_ids.add(review_id)


def _cover_patch_reference(value: Any, review_items: dict[str, dict[str, Any]], rows_to_review_ids: dict[int, set[str]], covered_ids: set[str]) -> None:
    """Mark review items covered by a patch reference.

    The preferred audit path is review_decisions[]. For compatibility with older,
    richer patch style, rows referenced in event edits/new events/removals,
    warnings_to_keep, human_review_needed, and blockers also count as reviewed.
    """
    if isinstance(value, str):
        item = review_items.get(value)
        if item:
            covered_ids.add(value)
            row = item.get("source_row")
            if isinstance(row, int):
                _add_covered_row(row, rows_to_review_ids, covered_ids)
        return

    if isinstance(value, int):
        _add_covered_row(value, rows_to_review_ids, covered_ids)
        return

    if not isinstance(value, dict):
        return

    review_id = value.get("review_id")
    if isinstance(review_id, str) and review_id in review_items:
        covered_ids.add(review_id)
        row = review_items[review_id].get("source_row")
        if isinstance(row, int):
            _add_covered_row(row, rows_to_review_ids, covered_ids)

    source_row = value.get("source_row")
    if isinstance(source_row, int):
        _add_covered_row(source_row, rows_to_review_ids, covered_ids)

    source_rows = value.get("source_rows")
    if isinstance(source_rows, list):
        for row in source_rows:
            if isinstance(row, int):
                _add_covered_row(row, rows_to_review_ids, covered_ids)


def _covered_review_item_ids(patch: dict[str, Any], review_packet: dict[str, Any] | None) -> set[str]:
    review_items = _review_items_by_id(review_packet)
    rows_to_review_ids: dict[int, set[str]] = {}
    for review_id, item in review_items.items():
        row = item.get("source_row")
        if isinstance(row, int):
            rows_to_review_ids.setdefault(row, set()).add(review_id)

    covered_ids: set[str] = set()
    for list_name in ["review_decisions", "event_edits", "new_events", "event_removals", "warnings_to_keep", "human_review_needed", "blockers"]:
        values = patch.get(list_name, [])
        if isinstance(values, list):
            for value in values:
                _cover_patch_reference(value, review_items, rows_to_review_ids, covered_ids)

    for list_name in ["reviewed_source_rows", "reviewed_rows"]:
        values = patch.get(list_name, [])
        if isinstance(values, list):
            for row in values:
                if isinstance(row, int):
                    _add_covered_row(row, rows_to_review_ids, covered_ids)

    for list_name in ["reviewed_review_ids", "review_ids_reviewed"]:
        values = patch.get(list_name, [])
        if isinstance(values, list):
            for review_id in values:
                if isinstance(review_id, str) and review_id in review_items:
                    covered_ids.add(review_id)

    debug_report = patch.get("debug_report")
    if isinstance(debug_report, dict):
        for list_name in ["reviewed_source_rows", "reviewed_rows"]:
            values = debug_report.get(list_name, [])
            if isinstance(values, list):
                for row in values:
                    if isinstance(row, int):
                        _add_covered_row(row, rows_to_review_ids, covered_ids)
        for list_name in ["reviewed_review_ids", "review_ids_reviewed"]:
            values = debug_report.get(list_name, [])
            if isinstance(values, list):
                for review_id in values:
                    if isinstance(review_id, str) and review_id in review_items:
                        covered_ids.add(review_id)
    return covered_ids


def _validate_review_item_coverage(patch: dict[str, Any], review_packet: dict[str, Any] | None) -> list[str]:
    """Reject patches that are syntactically valid but do not actually review the packet.

    A patch can be small because it only describes differences from the Python draft.
    However, when the review packet contains review_items, the patch must account for
    each item through review_decisions or a source-row reference in a patch section.
    This blocks no-op/minimal patches from silently rendering the untouched draft.
    """
    items = _review_item_order(review_packet)
    if not items:
        return []

    review_ids = [item.get("review_id") for item in items if isinstance(item.get("review_id"), str) and item.get("review_id")]
    if not review_ids:
        return []

    covered_ids = _covered_review_item_ids(patch, review_packet)
    missing = [review_id for review_id in review_ids if review_id not in covered_ids]
    if not missing:
        return []

    shown = ", ".join(missing[:12])
    if len(missing) > 12:
        shown += f", ... +{len(missing) - 12} more"
    return [
        "AI patch did not account for "
        f"{len(missing)} of {len(review_ids)} review_packet.review_items. "
        "This patch may be only a thin/no-op patch. Add one review_decisions entry per review item, "
        "or reference each item's source_row in new_events, event_edits, event_removals, "
        "warnings_to_keep, human_review_needed, blockers, or reviewed_source_rows. "
        f"Missing review_ids: {shown}"
    ]


def validate_patch(patch: dict[str, Any], draft: dict[str, Any], review_packet: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(patch, dict):
        return ["AI patch JSON root must be an object"]

    if "events" in patch and not PATCH_REQUIRED_KEYS.issubset(set(patch)):
        errors.append("Patch appears to be a full replacement timeline JSON; expected patch JSON")

    missing = PATCH_REQUIRED_KEYS - set(patch)
    if missing:
        errors.append(f"Patch missing keys: {sorted(missing)}")

    if not isinstance(patch.get("debug_report"), dict):
        errors.append("patch.debug_report must be an object")

    existing_events = _draft_events_by_id(draft)
    existing_ids = set(existing_events)
    known_rows = _known_source_rows(draft, review_packet)
    dates_by_row, fields_by_row = _source_support(draft, review_packet)

    event_edits = patch.get("event_edits", [])
    if not isinstance(event_edits, list):
        errors.append("patch.event_edits must be a list")
    else:
        for idx, edit in enumerate(event_edits, start=1):
            if not isinstance(edit, dict):
                errors.append(f"event_edits[{idx}] must be an object")
                continue
            event_id = edit.get("event_id")
            if event_id not in existing_ids:
                errors.append(f"event_edits[{idx}].event_id does not exist: {event_id}")
            changes = edit.get("changes")
            if not isinstance(changes, dict) or not changes:
                errors.append(f"event_edits[{idx}].changes must be a non-empty object")
            else:
                unsupported = set(changes) - PATCH_ALLOWED_EDIT_FIELDS
                if unsupported:
                    errors.append(f"event_edits[{idx}].changes contains unsupported fields: {sorted(unsupported)}")
                if "lane" in changes and changes["lane"] not in EVENT_LANES:
                    errors.append(f"event_edits[{idx}].changes.lane has invalid value")
                if "confidence" in changes and (not isinstance(changes["confidence"], (int, float)) or changes["confidence"] < 0 or changes["confidence"] > 1):
                    errors.append(f"event_edits[{idx}].changes.confidence must be 0..1")
                if "inferred" in changes and not isinstance(changes["inferred"], bool):
                    errors.append(f"event_edits[{idx}].changes.inferred must be boolean")
            if not isinstance(edit.get("reason"), str) or not edit.get("reason", "").strip():
                errors.append(f"event_edits[{idx}].reason is required")
            source_rows = _integer_list(edit.get("source_rows"))
            if source_rows is None:
                errors.append(f"event_edits[{idx}].source_rows must be a non-empty integer list")
            elif known_rows and any(row not in known_rows for row in source_rows):
                errors.append(f"event_edits[{idx}].source_rows contains rows not present in draft/review packet: {source_rows}")
            if event_id in existing_events and source_rows is not None:
                original_rows = _event_rows(existing_events[event_id])
                if original_rows and not original_rows.intersection(source_rows):
                    errors.append(f"event_edits[{idx}].source_rows must overlap original event source_rows {sorted(original_rows)}")

    new_events = patch.get("new_events", [])
    if not isinstance(new_events, list):
        errors.append("patch.new_events must be a list")
    else:
        for idx, event in enumerate(new_events, start=1):
            errors.extend(_event_errors(event, idx, prefix="new_events"))
            if not isinstance(event, dict):
                continue
            if event.get("event_id") in existing_ids:
                errors.append(f"new_events[{idx}].event_id already exists: {event.get('event_id')}")
            source_rows = _integer_list(event.get("source_rows"))
            if source_rows is not None:
                if known_rows and any(row not in known_rows for row in source_rows):
                    errors.append(f"new_events[{idx}].source_rows contains rows not present in draft/review packet: {source_rows}")
                supported_dates = set().union(*(dates_by_row.get(row, set()) for row in source_rows)) if dates_by_row else set()
                if supported_dates and event.get("date") not in supported_dates:
                    errors.append(
                        f"new_events[{idx}].date {event.get('date')} is not supported by Created/Resolved/comment/draft dates for source_rows {source_rows}: {sorted(supported_dates)}"
                    )

    event_removals = patch.get("event_removals", [])
    if not isinstance(event_removals, list):
        errors.append("patch.event_removals must be a list")
    else:
        for idx, removal in enumerate(event_removals, start=1):
            if not isinstance(removal, dict):
                errors.append(f"event_removals[{idx}] must be an object")
                continue
            event_id = removal.get("event_id")
            if event_id not in existing_ids:
                errors.append(f"event_removals[{idx}].event_id does not exist: {event_id}")
            if not isinstance(removal.get("reason"), str) or not removal.get("reason", "").strip():
                errors.append(f"event_removals[{idx}].reason is required")
            source_rows = _integer_list(removal.get("source_rows"))
            if source_rows is None:
                errors.append(f"event_removals[{idx}].source_rows must be a non-empty integer list")
            elif event_id in existing_events:
                original_rows = _event_rows(existing_events[event_id])
                if original_rows and not original_rows.intersection(source_rows):
                    errors.append(f"event_removals[{idx}].source_rows must overlap original event source_rows {sorted(original_rows)}")

    for list_name in ["warnings_to_keep", "human_review_needed", "blockers"]:
        if not isinstance(patch.get(list_name, []), list):
            errors.append(f"patch.{list_name} must be a list")

    if "review_decisions" in patch:
        errors.extend(_validate_review_decisions(patch, review_packet))

    errors.extend(_validate_review_item_coverage(patch, review_packet))

    return errors
