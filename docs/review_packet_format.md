# Review Packet Format

A review packet is optimized for AI review without requiring the AI to parse the raw CSV from scratch.

Root fields:

- `source_file`
- `draft_timeline_file`
- `generated_at`
- `review_threshold`
- `draft_summary`
- `review_items`
- `low_confidence_events`
- `warnings`
- `instructions_summary`

Each `review_item` includes:

- `review_id`
- `reason`
- `source_row`
- `issue_key`
- `issue_type`
- `summary`
- `created`
- `resolved`
- `status`
- `assignee`
- `priority`
- `labels`
- `description`
- `comments`
- `python_suggestion`
- `allowed_actions`

Allowed AI decisions include creating events, editing draft events, removing draft events, keeping warnings, and marking items for human review. The AI communicates those decisions through patch JSON, not a full replacement timeline.

## AI patch decision audit

`review_decisions` is the preferred audit trail for review items. When the review packet contains `review_items`, the AI should include one decision per `review_id`. Python still applies the top-level patch arrays, not the decisions themselves, but patch validation rejects thin/no-op patches that do not account for all review items.

Allowed decision actions:

- `create_event`
- `edit_event`
- `remove_event`
- `keep_warning`
- `mark_needs_human_review`
- `no_change`

When an action creates, edits, or removes an event, the matching event ID should also appear in the corresponding top-level patch array. For `keep_warning`, `mark_needs_human_review`, or `no_change`, a concise decision can be enough because the draft warnings remain traceable. Python validates the decision entries if they are present.
