#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets" / "series_5" / "tools"))
from workspace import activate
activate()
from evaluate_class1_corrections import decode_runs, metric_counts, metrics, safe_file, load_references, candidate_diagnostics


class CorrectionTests(unittest.TestCase):
    def test_candidate_ties_do_not_create_false_class_assignment_failure(self):
        ref = np.array([[1, 1, 0]], np.uint8)
        masks = [({"class_id": cid, "raw_sam_mask": str(cid), "phrase": str(cid)}, ref == 1) for cid in (3, 1)]
        result = candidate_diagnostics(masks, ref)
        self.assertEqual(result["equally_best_class_ids"], [1, 3])
        self.assertEqual(result["class1_iou_gap"], 0)
        self.assertEqual(result["best_class1_iou"], 1)
        self.assertIsNone(candidate_diagnostics([], ref))

    def test_browser_runs_round_trip_and_raw_hash(self):
        pixels = decode_runs([0, 2, 1, 2, 255, 2], (2, 3))
        np.testing.assert_array_equal(pixels, [[0, 0, 1], [1, 255, 255]])
        self.assertEqual(hashlib.sha256(pixels.tobytes()).hexdigest(), hashlib.sha256(bytes([0, 0, 1, 1, 255, 255])).hexdigest())

    def test_bad_runs_rejected(self):
        for value in (None, [], [1], [1, 0], [1, -1], [1, 7], [1, 5], [1, 6.0], [True, 6], [2, 6], [1, True], [1, float("nan")]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_runs(value, (2, 3))

    def test_reference_uncertainty_excluded_not_prediction_abstention(self):
        ref = np.array([[1, 1, 0, 0, 255]], dtype=np.uint8)
        pred = np.array([[True, False, True, False, True]])
        scores = metrics(pred, ref)
        self.assertEqual({k: scores[k] for k in ("tp", "fp", "fn", "tn", "ignored")}, {"tp": 1, "fp": 1, "fn": 1, "tn": 1, "ignored": 1})
        self.assertEqual(scores["iou"], 1/3)
        self.assertEqual(scores["f1"], .5)
        self.assertEqual(metrics(np.zeros_like(pred), ref)["fn"], 2)

    def test_empty_and_all_ignored_are_not_perfect_scores(self):
        for ref in (np.zeros((2, 2), np.uint8), np.full((2, 2), 255, np.uint8)):
            self.assertIsNone(metrics(np.zeros((2, 2), bool), ref)["iou"])

    def test_nonbinary_predictions_and_shape_mismatch_rejected(self):
        ref = np.zeros((2, 2), np.uint8)
        for pred in (np.zeros((2, 2), np.uint8), np.zeros((2, 1), bool)):
            with self.assertRaises(ValueError):
                metric_counts(pred, ref)
        with self.assertRaises(ValueError):
            metric_counts(np.zeros((2, 2), bool), np.full((2, 2), 2))

    def test_asset_path_cannot_escape_input_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "inside").mkdir(); (root / "outside").write_text("x")
            for path in ("../outside", str(root / "outside")):
                with self.assertRaises(ValueError):
                    safe_file(root / "inside", path)

    def test_draft_not_promoted_without_explicit_option(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps({"created_utc":"test", "contract":{"source_names_sha256":"names"}}))
            entry = {"image":"test.jpg", "size":[2, 2], "source_sha256":"source", "base_mask_sha256":"mask", "status":"draft"}
            selection = {"baseline":str(root), "images":["test.jpg"], "frames":[{"image":"test.jpg", "record":{"size":[2,2], "source_sha256":"source", "mask_sha256":"mask"}}]}
            export = {"schema":"sidewalkpilot-class1-corrections-v1", "dataset_key":"sp-review:test:names", "annotation_scope":{"kind":"binary_class_reference", "positive_class_id":1, "not_a_12_class_mask":True}, "entries":[entry]}
            path = root / "export.json"; path.write_text(json.dumps(export))
            with self.assertRaisesRegex(ValueError, "drafts"):
                load_references(path, selection, False)


if __name__ == "__main__":
    unittest.main()
