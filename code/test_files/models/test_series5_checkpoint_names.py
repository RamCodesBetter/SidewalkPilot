import errno
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"))
from workspace import activate
activate()
import checkpoint_names as naming


class CheckpointNamesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write("config.json", dict(model_name="5.C", smoke_only=False))
        self.write("status.json", dict(status="complete", epochs_completed=3,
                                       best_validation_sidewalk_iou=.9, early_stopped=True))
        self.write("history.json", [dict(epoch=i, validation_sidewalk_iou=v)
                                    for i, v in enumerate((.9, .9, .8), 1)])
        (self.root / "best.pt").write_bytes(b"best epoch 1")
        (self.root / "last.pt").write_bytes(b"end epoch 3")

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def test_names_support_beta_and_release_and_reject_paths_or_suffixes(self):
        self.assertEqual(naming.checkpoint_names("5.C"), dict(end="5.C", best_iou="5.Cb", smart="5.Cs"))
        self.assertEqual(naming.checkpoint_names("5.0")["smart"], "5.0s")
        for name in ("../5.C", "5.Cb", "5.Cs", "5.c", "5.#"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                naming.checkpoint_names(name)

    def test_completed_run_publishes_end_and_first_best_tie_but_no_smart(self):
        record = naming.publish_completed_run(self.root, "5.C")
        self.assertEqual((self.root / "5.C.pt").read_bytes(), b"end epoch 3")
        self.assertEqual((self.root / "5.Cb.pt").read_bytes(), b"best epoch 1")
        self.assertEqual(record["artifacts"]["end"]["epoch"], 3)
        self.assertEqual(record["artifacts"]["best_iou"]["epoch"], 1)
        self.assertTrue(record["early_stopped"])
        self.assertFalse(record["test_used_for_selection"])
        self.assertEqual(record["artifacts"]["smart"]["status"], "reserved")
        self.assertFalse((self.root / "5.Cs.pt").exists())
        self.assertEqual(json.loads((self.root / "checkpoint-selection.json").read_text()), record)
        self.assertEqual(naming.publish_completed_run(self.root, "5.C"), record)

    def test_snapshot_does_not_follow_later_atomic_replacement(self):
        naming.publish_completed_run(self.root, "5.C")
        replacement = self.root / "replacement.tmp"
        replacement.write_bytes(b"later resume")
        replacement.replace(self.root / "last.pt")
        self.assertEqual((self.root / "5.C.pt").read_bytes(), b"end epoch 3")

    def test_copy_fallback_on_unsupported_hardlinks(self):
        with patch.object(Path, "hardlink_to", side_effect=OSError(errno.ENOTSUP, "unsupported")):
            naming.publish_completed_run(self.root, "5.C")
        self.assertEqual((self.root / "5.Cb.pt").read_bytes(), b"best epoch 1")
        self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_smoke_interrupted_and_wrong_model_cannot_publish(self):
        for smoke, status, model in ((True, "complete", "5.C"),
                                     (False, "interrupted", "5.C"), (False, "complete", "5.D")):
            self.write("config.json", dict(model_name=model, smoke_only=smoke))
            self.write("status.json", dict(status=status))
            with self.subTest(smoke=smoke, status=status, model=model), self.assertRaises(ValueError):
                naming.publish_completed_run(self.root, "5.C")
        self.assertFalse((self.root / "5.C.pt").exists())

    def test_missing_checkpoint_preflight_does_not_publish_partial_pair(self):
        (self.root / "best.pt").unlink()
        with self.assertRaises(FileNotFoundError):
            naming.publish_completed_run(self.root, "5.C")
        self.assertFalse((self.root / "5.C.pt").exists())

    def test_invalid_history_or_status_cannot_publish(self):
        for history in ([], [dict(epoch=1, validation_sidewalk_iou=float("nan"))] * 3,
                        [dict(epoch=i, validation_sidewalk_iou=.7) for i in range(1, 4)]):
            self.write("history.json", history)
            with self.subTest(history=history), self.assertRaises(ValueError):
                naming.publish_completed_run(self.root, "5.C")
        self.assertFalse((self.root / "checkpoint-selection.json").exists())


if __name__ == "__main__":
    unittest.main()
