"""Helpers for manual AI review packet UX."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import PROMPT_PATH


def load_review_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return "Return only valid Timeline Builder AI patch JSON. Do not return a full replacement timeline JSON."


def copy_prompt_text(*, draft_path: Path | None = None, packet_path: Path | None = None, patch_path: Path | None = None) -> str:
    """Text intended for the GUI Copy Prompt + Packet Instructions button."""
    parts = [load_review_prompt().strip(), "", "## Files for this review"]
    if draft_path:
        parts.append(f"Draft timeline JSON: `{draft_path}`")
    if packet_path:
        parts.append(f"Review packet JSON: `{packet_path}`")
    if patch_path:
        parts.append(f"Save your response as patch JSON here: `{patch_path}`")
    parts.extend(
        [
            "",
            "Please review the packet and return only valid patch JSON. Do not paste prose before or after the JSON.",
            "Do not include the full reviewed timeline JSON; Python will apply and validate the patch.",
        ]
    )
    return "\n".join(parts) + "\n"


def count_non_incident_review_items(review_packet: dict[str, Any] | None) -> int:
    if not isinstance(review_packet, dict):
        return 0
    count = 0
    for item in review_packet.get("review_items", []):
        if not isinstance(item, dict):
            continue
        issue_type = str(item.get("issue_type") or "").strip().lower()
        reason = str(item.get("reason") or "").lower()
        if issue_type and issue_type != "incident":
            count += 1
        elif "non-incident" in reason or "non incident" in reason:
            count += 1
    return count
