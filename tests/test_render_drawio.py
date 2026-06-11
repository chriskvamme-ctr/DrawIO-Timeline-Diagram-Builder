import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class RenderDrawioSmokeTest(unittest.TestCase):
    def test_sample_json_validates_and_renders(self):
        sample = ROOT / "examples" / "sample_timeline.json"
        renderer = ROOT / "scripts" / "render_drawio.py"
        validator = ROOT / "scripts" / "validate_timeline_json.py"

        subprocess.run([sys.executable, str(validator), str(sample)], check=True, cwd=ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.drawio"
            subprocess.run([sys.executable, str(renderer), str(sample), str(output)], check=True, cwd=ROOT)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1000)
            tree = ET.parse(output)
            self.assertEqual(tree.getroot().tag, "mxfile")


    def test_event_cards_use_compact_visible_text(self):
        from timeline_builder.drawio_renderer import render_data

        data = {
            "unit_id": "UNIT-42",
            "source_file": "unit.csv",
            "date_range": {"start": "2022-01-18", "end": "2022-01-18"},
            "lanes": ["incident", "date", "component_replacement", "other"],
            "events": [
                {
                    "event_id": "E001",
                    "lane": "other",
                    "date": "2022-01-18",
                    "end_date": None,
                    "title": "Escalated issue with follow up meeting and customer escalation",
                    "details": "18/Jan/22 8:50 AM;[~accountid:abc123] Kicked off escalation meeting with a very long comment body that should not be visible in the card.",
                    "issue_key": "DIG-123",
                    "component": None,
                    "source_rows": [140],
                    "source_fields": ["Comment.2"],
                    "confidence": 0.9,
                    "inferred": False,
                }
            ],
            "warnings": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "compact.drawio"
            render_data(data, output)
            tree = ET.parse(output)
            event_values = [cell.attrib.get("value", "") for cell in tree.iter("mxCell") if "Escalated issue" in cell.attrib.get("value", "")]
            self.assertEqual(len(event_values), 1)
            value = event_values[0]
            self.assertIn("<br/>", value)
            self.assertIn("Ticket: DIG-123", value)
            self.assertIn("Src: R140 · Comment.2", value)
            self.assertNotIn("18/Jan/22 8:50 AM", value)
            self.assertNotIn("accountid", value)
            self.assertNotIn("Kicked off escalation", value)
            self.assertNotIn("Rows:", value)

    def test_ticket_label_falls_back_to_key_in_title(self):
        from timeline_builder.drawio_renderer import card_visible_lines

        event = {
            "event_id": "AI-R0001",
            "title": "DIG-456 - Rechecked unit after repair",
            "issue_key": None,
            "source_rows": [12],
            "source_fields": ["Comment"],
        }
        lines = card_visible_lines(event)
        self.assertIn("Ticket: DIG-456", lines)


    def test_connectors_render_behind_event_cards(self):
        from timeline_builder.drawio_renderer import render_data

        data = {
            "unit_id": "UNIT-42",
            "source_file": "unit.csv",
            "date_range": {"start": "2022-01-18", "end": "2022-01-18"},
            "lanes": ["incident", "date", "component_replacement", "other"],
            "events": [
                {
                    "event_id": "E001",
                    "lane": "other",
                    "date": "2022-01-18",
                    "end_date": None,
                    "title": "Escalated issue",
                    "details": "details hidden from card",
                    "issue_key": "DIG-123",
                    "component": None,
                    "source_rows": [140],
                    "source_fields": ["Comment.2"],
                    "confidence": 0.9,
                    "inferred": False,
                }
            ],
            "warnings": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "zorder.drawio"
            render_data(data, output)
            tree = ET.parse(output)
            root_cells = list(tree.getroot().find("diagram/mxGraphModel/root"))
            edge_indexes = [idx for idx, cell in enumerate(root_cells) if cell.attrib.get("edge") == "1"]
            event_indexes = [idx for idx, cell in enumerate(root_cells) if "Escalated issue" in cell.attrib.get("value", "")]
            self.assertTrue(edge_indexes)
            self.assertTrue(event_indexes)
            self.assertLess(max(edge_indexes), min(event_indexes))

    def test_sample_json_has_version_expected_shape(self):
        sample = ROOT / "examples" / "sample_timeline.json"
        with sample.open("r", encoding="utf-8") as file:
            data = json.load(file)
        self.assertEqual(data["lanes"], ["incident", "date", "component_replacement", "other"])
        self.assertTrue(data["events"])


if __name__ == "__main__":
    unittest.main()
