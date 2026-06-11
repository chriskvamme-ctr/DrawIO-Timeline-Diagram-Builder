import unittest

from timeline_builder.ai_patch import apply_patch
from timeline_builder.validation import validate_patch


class PatchValidationGuardrailTest(unittest.TestCase):
    def _draft_and_packet(self):
        draft = {
            "unit_id": "unit",
            "source_file": "unit.csv",
            "date_range": {"start": "2026-01-02", "end": "2026-01-02"},
            "lanes": ["incident", "date", "component_replacement", "other"],
            "events": [
                {
                    "event_id": "E0001",
                    "lane": "incident",
                    "date": "2026-01-02",
                    "end_date": None,
                    "title": "DIG-1 - Encoder fault",
                    "details": "Status: Open",
                    "issue_key": "DIG-1",
                    "component": None,
                    "source_rows": [1],
                    "source_fields": ["Issue key", "Summary", "Created"],
                    "confidence": 0.97,
                    "inferred": False,
                }
            ],
            "warnings": [{"source_row": 2, "reason": "Needs review", "action": "needs_review"}],
        }
        packet = {
            "review_items": [
                {
                    "review_id": "R0001",
                    "source_row": 2,
                    "created": "1/4/26",
                    "resolved": None,
                    "issue_key": "DIG-2",
                    "comments": [{"field": "Comment", "date": "2026-01-04", "text": "Check with team"}],
                }
            ],
            "low_confidence_events": [],
            "warnings": [{"source_row": 2, "reason": "Needs review", "action": "needs_review"}],
        }
        return draft, packet

    def _base_patch(self):
        return {
            "summary": "reviewed",
            "debug_report": {"received_review_items": 1, "non_incident_rows_seen": 1},
            "review_decisions": [
                {
                    "review_id": "R0001",
                    "action": "keep_warning",
                    "reason": "No clear event.",
                    "source_rows": [2],
                }
            ],
            "event_edits": [],
            "new_events": [],
            "event_removals": [],
            "warnings_to_keep": ["R0001"],
            "human_review_needed": [],
            "blockers": [],
        }

    def test_old_style_patch_without_review_decisions_is_accepted(self):
        draft, packet = self._draft_and_packet()
        patch = self._base_patch()
        patch.pop("review_decisions")
        errors = validate_patch(patch, draft, review_packet=packet)
        self.assertFalse(errors, errors)

    def test_empty_optional_review_decisions_is_accepted(self):
        draft, packet = self._draft_and_packet()
        patch = self._base_patch()
        patch["review_decisions"] = []
        errors = validate_patch(patch, draft, review_packet=packet)
        self.assertFalse(errors, errors)


    def test_tiny_noop_patch_without_review_coverage_is_rejected(self):
        draft, packet = self._draft_and_packet()
        patch = self._base_patch()
        patch.pop("review_decisions")
        patch["warnings_to_keep"] = []
        patch["debug_report"] = {"received_review_items": 1, "non_incident_rows_seen": 1}
        errors = validate_patch(patch, draft, review_packet=packet)
        self.assertTrue(any("did not account" in error for error in errors), errors)

    def test_reviewed_source_rows_can_cover_legacy_patch(self):
        draft, packet = self._draft_and_packet()
        patch = self._base_patch()
        patch.pop("review_decisions")
        patch["warnings_to_keep"] = []
        patch["reviewed_source_rows"] = [2]
        errors = validate_patch(patch, draft, review_packet=packet)
        self.assertFalse(errors, errors)


    def test_apply_patch_fills_missing_issue_key_from_review_packet(self):
        draft, packet = self._draft_and_packet()
        patch = self._base_patch()
        patch["review_decisions"] = [
            {
                "review_id": "R0001",
                "action": "create_event",
                "new_event_id": "AI-R0001",
                "reason": "Clear action from reviewed row.",
                "source_rows": [2],
            }
        ]
        patch["new_events"] = [
            {
                "event_id": "AI-R0001",
                "lane": "other",
                "date": "2026-01-04",
                "end_date": None,
                "title": "Checked with team",
                "details": "Created from the reviewed packet row.",
                "issue_key": None,
                "component": None,
                "source_rows": [2],
                "source_fields": ["Comment"],
                "confidence": 0.85,
                "inferred": False,
            }
        ]
        reviewed = apply_patch(draft, patch, review_packet=packet)
        created = next(event for event in reviewed["events"] if event["event_id"] == "AI-R0001")
        self.assertEqual(created["issue_key"], "DIG-2")

    def test_new_event_with_unsupported_date_is_rejected(self):
        draft, packet = self._draft_and_packet()
        patch = self._base_patch()
        patch["review_decisions"] = [
            {
                "review_id": "R0001",
                "action": "create_event",
                "new_event_id": "AI-R0001",
                "reason": "Claims a new event.",
                "source_rows": [2],
            }
        ]
        patch["new_events"] = [
            {
                "event_id": "AI-R0001",
                "lane": "other",
                "date": "2026-01-07",
                "end_date": None,
                "title": "Checked with team",
                "details": "Unsupported date should be rejected.",
                "issue_key": "DIG-2",
                "component": None,
                "source_rows": [2],
                "source_fields": ["Comment"],
                "confidence": 0.85,
                "inferred": False,
            }
        ]
        errors = validate_patch(patch, draft, review_packet=packet)
        self.assertTrue(any("not supported" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
