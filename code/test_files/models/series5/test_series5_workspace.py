from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3] / "ai_models_datasets/series_5/tools"
sys.path.insert(0, str(ROOT))
from workspace import activate, source_path
activate()
from label_grounded_sam2 import DEFAULT_SOURCE


class WorkspaceTests(unittest.TestCase):
    def test_entry_points_work_from_an_unrelated_directory(self):
        paths = [ROOT.parent / f"series_5_{name}_sidewalkpilot_trainer.py" for name in "abce"]
        paths += [source_path(f"{name}.py") for name in (
            "export_series5_models", "screen_full_inventory",
            "package_model_lab", "serve_df_history", "prepare_series5_pseudo_dataset")]
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
