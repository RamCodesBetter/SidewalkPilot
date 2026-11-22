from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"
sys.path.insert(0, str(ROOT))
from organize_workspace import organize, snapshot
from label_grounded_sam2 import DEFAULT_SOURCE


class WorkspaceTests(unittest.TestCase):
    def test_moved_labeler_still_finds_original_dataset(self):
        self.assertEqual(DEFAULT_SOURCE, ROOT.parents[1] / "series_3_and_4/sidewalkpilot_dataset")

    def test_dry_run_does_not_move_or_create(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "5.a-test").mkdir()
            (root / "5.a-test/index.html").write_text("viewer")
            result = organize(root)
            self.assertEqual(result["verified_files"], 1)
            self.assertFalse(result["applied"])
            self.assertFalse((root / "reviews").exists())

    def test_moves_preserve_bytes_and_second_run_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "5.a-test").mkdir()
            (root / "5.a-test/review.json").write_text('{"decision": "correct"}')
            (root / "manifest.json").write_text('{"historical_path": "unchanged"}')
            (root / "images").mkdir()
            (root / "images/image.JPG").write_bytes(b"original-image")
            before = snapshot(root / "images")
            result = organize(root, True)
            self.assertEqual(result["moved_items"], 3)
            self.assertEqual(snapshot(root / "reviews/legacy-class1/images"), before)
            self.assertEqual((root / "reviews/legacy-class1/manifest.json").read_text(),
                             '{"historical_path": "unchanged"}')
            journal = (root / "workspace-migration.json").read_bytes()
            self.assertEqual(organize(root, True)["moved_items"], 0)
            self.assertEqual((root / "workspace-migration.json").read_bytes(), journal)

    def test_collision_is_detected_before_any_moves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "5.a-test").mkdir()
            (root / "5.a-vs-5.b").mkdir()
            (root / "reviews/5.a-vs-5.b").mkdir(parents=True)
            with self.assertRaises(FileExistsError):
                organize(root, True)
            self.assertTrue((root / "5.a-test").exists())

    def test_symlink_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            root.mkdir()
            (root / "reviews").symlink_to(Path(directory), target_is_directory=True)
            with self.assertRaises(ValueError):
                organize(root, True)

    def test_generated_files_do_not_modify_source_or_unknown_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools/review").mkdir(parents=True)
            (root / "tools/taxonomy.json").write_text('{}')
            (root / "tools/review/index.html").write_text('viewer')
            (root / "manifest.json").write_text('{}')
            (root / "my-notes.txt").write_text('keep')
            before = snapshot(root / "tools")
            organize(root, True)
            self.assertEqual(snapshot(root / "tools"), before)
            self.assertEqual((root / "my-notes.txt").read_text(), 'keep')
            self.assertEqual((root / "reviews/legacy-class1/taxonomy.json").read_text(), '{}')


if __name__ == "__main__":
    unittest.main()
