from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"
sys.path.insert(0, str(ROOT))
from workspace import activate, source_path
activate()
from organize_workspace import organize, snapshot
from label_grounded_sam2 import DEFAULT_SOURCE


class WorkspaceTests(unittest.TestCase):
    def test_entry_points_work_from_an_unrelated_directory(self):
        paths = [ROOT.parent / f"series_5_{name}_sidewalkpilot_trainer.py" for name in "abc"]
        paths += [source_path(f"{name}.py") for name in (
            "compare_series5_betas", "export_series5_models", "package_model_review",
            "package_beta_comparison", "prepare_series5_pseudo_dataset")]
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory() as directory:
            for path in paths:
                with self.subTest(script=path.name):
                    result = subprocess.run([sys.executable, str(path), "--help"], cwd=directory,
                                            env=env, capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout.lower())

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
            self.assertFalse((root / "notebook").exists())

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
            (root / "tools/configs").mkdir()
            (root / "tools/configs/taxonomy.json").write_text('{}')
            (root / "tools/review/index.html").write_text('viewer')
            (root / "manifest.json").write_text('{}')
            (root / "my-notes.txt").write_text('keep')
            before = snapshot(root / "tools")
            organize(root, True)
            self.assertEqual(snapshot(root / "tools"), before)
            self.assertEqual((root / "my-notes.txt").read_text(), 'keep')
            self.assertEqual((root / "reviews/legacy-class1/taxonomy.json").read_text(), '{}')

    def test_source_lookup_rejects_paths_and_missing_files(self):
        for name in ("../workspace.py", "review/index.html", "a\\b.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                source_path(name)
        with self.assertRaises(FileNotFoundError):
            source_path("missing-source-file.py")

    def test_every_source_has_an_unambiguous_lookup(self):
        for path in ROOT.rglob("*"):
            if path.suffix in (".py", ".json") and "__pycache__" not in path.parts:
                with self.subTest(path=path):
                    self.assertEqual(source_path(path.name), path)


if __name__ == "__main__":
    unittest.main()
