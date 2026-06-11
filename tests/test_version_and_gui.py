import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VersionAndGuiTest(unittest.TestCase):
    def test_package_version_comes_from_version_file(self):
        from timeline_builder import __version__

        self.assertEqual(__version__, (ROOT / "VERSION").read_text(encoding="utf-8").strip())

    def test_cli_version_matches_version_file(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "timeline_builder.py"), "--version"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn(version, result.stdout)

    def test_gui_title_uses_package_version_not_hardcoded_version(self):
        text = (ROOT / "tools" / "timeline_builder_gui.py").read_text(encoding="utf-8")
        self.assertIn("from timeline_builder import __version__", text)
        self.assertIn("APP_TITLE = f\"Timeline Builder v{__version__}", text)
        self.assertIsNone(re.search(r"Timeline Builder v0\.\d+\.\d+", text))

    def test_gui_normal_flow_has_one_primary_action_per_stage(self):
        text = (ROOT / "tools" / "timeline_builder_gui.py").read_text(encoding="utf-8")
        for label in [
            "Prepare AI Packet + Copy Prompt",
            "Select AI Patch + Check + Render",
            "Open in draw.io",
        ]:
            self.assertIn(label, text)
        for old_button in [
            "Apply AI Patch",
            "Validate Reviewed JSON",
            "Run Quality Gates",
            "Render draw.io",
            "Export SVG Preview",
            "Load AI Patch JSON",
        ]:
            self.assertNotIn(old_button, text)


if __name__ == "__main__":
    unittest.main()
