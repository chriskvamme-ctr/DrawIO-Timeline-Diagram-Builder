"""Shared constants for the Timeline Builder pipeline."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LANES = ["incident", "date", "component_replacement", "other"]
EVENT_LANES = {"incident", "component_replacement", "other"}
DEFAULT_REVIEW_THRESHOLD = 0.85

WARNING_ACTIONS = {"not_rendered", "needs_review", "duplicate_merged"}
PATCH_ALLOWED_EDIT_FIELDS = {"title", "details", "lane", "component", "confidence", "inferred"}
PATCH_REQUIRED_KEYS = {
    "summary",
    "debug_report",
    "event_edits",
    "new_events",
    "event_removals",
    "warnings_to_keep",
    "human_review_needed",
    "blockers",
}

REVIEW_DECISION_ACTIONS = {
    "create_event",
    "edit_event",
    "remove_event",
    "keep_warning",
    "mark_needs_human_review",
    "no_change",
}

ALLOWED_REVIEW_ACTIONS = [
    "create event",
    "edit event",
    "remove event",
    "keep warning",
    "mark needs human review",
]

PROMPT_PATH = PROJECT_ROOT / "prompts" / "review_timeline_packet.md"
