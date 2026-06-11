import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "timeline_builder.py"


class TimelineBuilderPipelineTest(unittest.TestCase):
    def test_prepare_apply_review_and_svg(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = tmp / "unit_42.csv"
            csv_path.write_text(
                "Issue key,Issue Type,Summary,Created,Resolved,Status,Assignee,Priority,Labels,Comment\n"
                "DIG-1,Incident,Encoder fault,1/2/26,,Open,Ada,High,robot,Replaced encoder cable on 1/3/26\n"
                "DIG-2,Task,Admin follow-up,1/4/26,,Open,Bob,Low,ops,Check with team\n",
                encoding="utf-8",
            )

            subprocess.run([sys.executable, str(CLI), "prepare", str(csv_path), "--output-folder", str(tmp)], check=True, cwd=ROOT)
            artifact_dir = tmp / "unit_42_timeline-diagram"
            ai_dir = artifact_dir / "ai-review"
            draft = artifact_dir / "unit_42_timeline_draft.json"
            packet = ai_dir / "unit_42_timeline_review_packet.json"
            prompt = ai_dir / "unit_42_timeline_ai_review_prompt.md"
            patch = ai_dir / "unit_42_timeline_ai_patch.json"
            self.assertTrue(artifact_dir.exists())
            self.assertTrue(ai_dir.exists())
            self.assertTrue(draft.exists())
            self.assertTrue(packet.exists())
            self.assertTrue(prompt.exists())
            packet_data = json.loads(packet.read_text(encoding="utf-8"))
            self.assertEqual(packet_data["draft_summary"]["non_incident_rows"], 1)
            self.assertTrue(packet_data["review_items"])

            patch.write_text(
                json.dumps(
                    {
                        "summary": "Reviewed packet; no timeline changes needed.",
                        "debug_report": {
                            "received_review_items": len(packet_data["review_items"]),
                            "non_incident_rows_seen": 1,
                            "low_confidence_events_seen": len(packet_data["low_confidence_events"]),
                            "warnings_seen": len(packet_data["warnings"]),
                            "created_events": 0,
                            "edited_events": 0,
                            "removed_events": 0,
                            "kept_warnings": len(packet_data["warnings"]),
                            "human_review_needed_count": 0,
                            "issue_type_observations": ["Task row was administrative."],
                            "blockers": [],
                        },
                        "review_decisions": [
                            {
                                "review_id": item["review_id"],
                                "action": "keep_warning",
                                "reason": "No clear dated timeline event is supported by this review item.",
                                "source_rows": [item["source_row"]],
                            }
                            for item in packet_data["review_items"]
                        ],
                        "event_edits": [],
                        "new_events": [],
                        "event_removals": [],
                        "warnings_to_keep": [item["review_id"] for item in packet_data["review_items"]],
                        "human_review_needed": [],
                        "blockers": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            subprocess.run([sys.executable, str(CLI), "apply-review", str(draft), str(patch)], check=True, cwd=ROOT)
            reviewed = artifact_dir / "unit_42_timeline_reviewed.json"
            report = artifact_dir / "unit_42_timeline_quality_report.json"
            self.assertTrue(reviewed.exists())
            report_data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(report_data["status"], "passed")

            subprocess.run([sys.executable, str(CLI), "render", str(reviewed)], check=True, cwd=ROOT)
            self.assertTrue((artifact_dir / "unit_42_timeline_reviewed.drawio").exists())
            subprocess.run([sys.executable, str(CLI), "export-svg", str(reviewed)], check=True, cwd=ROOT)
            self.assertTrue((artifact_dir / "unit_42_timeline_reviewed.svg").exists())


if __name__ == "__main__":
    unittest.main()
