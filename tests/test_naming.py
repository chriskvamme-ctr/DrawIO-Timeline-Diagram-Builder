import tempfile
import unittest
from pathlib import Path

from timeline_builder.naming import AI_REVIEW_FOLDER_NAME, ARTIFACT_FOLDER_SUFFIX, csv_artifact_paths


class NamingTest(unittest.TestCase):
    def test_csv_artifact_paths_create_per_csv_folder_and_ai_subfolder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            paths = csv_artifact_paths(tmp / "digit_142_history.csv", tmp)
            artifact_dir = tmp / f"digit_142_history{ARTIFACT_FOLDER_SUFFIX}"
            ai_dir = artifact_dir / AI_REVIEW_FOLDER_NAME

            self.assertEqual(paths.artifact_folder, artifact_dir)
            self.assertEqual(paths.ai_review_folder, ai_dir)
            self.assertEqual(paths.draft, artifact_dir / "digit_142_history_timeline_draft.json")
            self.assertEqual(paths.review_packet, ai_dir / "digit_142_history_timeline_review_packet.json")
            self.assertEqual(paths.ai_prompt, ai_dir / "digit_142_history_timeline_ai_review_prompt.md")
            self.assertEqual(paths.ai_patch, ai_dir / "digit_142_history_timeline_ai_patch.json")
            self.assertEqual(paths.drawio, artifact_dir / "digit_142_history_timeline_reviewed.drawio")

    def test_existing_artifact_folder_is_not_nested_again(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            artifact_dir = tmp / f"digit_142_history{ARTIFACT_FOLDER_SUFFIX}"
            paths = csv_artifact_paths(tmp / "digit_142_history.csv", artifact_dir)
            self.assertEqual(paths.artifact_folder, artifact_dir)
            self.assertNotIn(f"{ARTIFACT_FOLDER_SUFFIX}{ARTIFACT_FOLDER_SUFFIX}", str(paths.base))


if __name__ == "__main__":
    unittest.main()
