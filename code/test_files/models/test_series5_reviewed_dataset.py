#!/usr/bin/env python3
"""Protect accepted-image reuse, evidence identity, and partial supervision."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))
from prepare_reviewed_dataset import (
    Inputs, binary_labels, candidate_pixels, pixel_counts, pixel_hash,
    prepare, select_candidate, sha256, verify_dataset,
)


class ReviewedDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.output = self.root / "dataset"
        self.number = 0

    def candidate(self, values, scope="class-1-only", correction=False):
        self.number += 1
        pixels = np.asarray(values, dtype=np.uint8)
        name = f"2026_07_02_run_1__photo_20260702_163850_{self.number:06d}.jpg"
        source = self.inputs / name
        Image.new("RGB", tuple(reversed(pixels.shape)), (self.number * 30, 100, 30)).save(source)
        mask = source.with_suffix(".png")
        Image.fromarray(pixels).save(mask)
        evidence = source.with_suffix(".json")
        value = {"schema": "fixture-review", "decision": "correct"}
        when = "2026-11-09T04:53:43+00:00"
        package = "fixture-package"
        if correction:
            scope = "binary-class1-reference"
            value = {
                "schema": "sidewalkpilot-class1-corrections-v1", "dataset_key": package,
                "annotation_scope": {"kind": "binary_class_reference", "positive_class_id": 1,
                                     "not_a_12_class_mask": True},
                "entries": [{"image": name, "source_sha256": sha256(source), "size": list(reversed(pixels.shape)),
                             "status": "reviewed", "updated_utc": when, "pixels_sha256": pixel_hash(pixels),
                             "pixels_rle": [part for v in pixels.flat for part in (int(v), 1)]}],
            }
        evidence.write_text(json.dumps(value))
        return {
            "source_name": name, "source_path": str(source), "source_sha256": sha256(source),
            "size": list(reversed(pixels.shape)), "mask_path": None if correction else str(mask),
            "mask_sha256": None if correction else sha256(mask),
            "mask_identity": "pixels:" + pixel_hash(pixels) if correction else "file:" + sha256(mask),
            "pixels_sha256": pixel_hash(pixels), "pixel_counts": pixel_counts(pixels),
            "scope": scope, "decision": "correct", "timestamp": when,
            "evidence_path": str(evidence), "evidence_sha256": sha256(evidence), "package_id": package,
        }

    def row(self, *candidates):
        return {**{key: candidates[0][key] for key in ("source_name", "source_sha256")},
                "accepted_mask_versions": len(candidates), "candidates": list(candidates)}

    def inventory(self, rows):
        path = self.inputs / "inventory.json"
        path.write_text(json.dumps({"summary": {"unique_accepted_images": len(rows)}, "images": rows}))
        return path

    def test_binary_uncertainty_is_preserved(self):
        pixels = np.array([[0, 1, 255]], dtype=np.uint8)
        labels, kind = binary_labels(pixels, "binary-class1-reference")
        np.testing.assert_array_equal(labels, pixels)
        self.assertEqual(kind, "binary-reference")
        self.assertFalse(np.shares_memory(labels, pixels))

    def test_unreviewed_classes_and_zero_become_ignore(self):
        pixels = np.array([[0, 1, 2, 11, 255]], dtype=np.uint8)
        labels, kind = binary_labels(pixels, "class-1-only")
        np.testing.assert_array_equal(labels, [[255, 1, 255, 255, 255]])
        np.testing.assert_array_equal(pixels, [[0, 1, 2, 11, 255]])
        self.assertEqual(kind, "sidewalk-positive-only")

    def test_positive_only_pixels_remain_unchanged(self):
        pixels = np.array([[1, 255, 1]], dtype=np.uint8)
        np.testing.assert_array_equal(binary_labels(pixels, "class-1-only")[0], pixels)

    def test_invalid_mask_scope_ids_dtype_and_shape_rejected(self):
        for pixels, scope in ((np.array([[2]], dtype=np.uint8), "binary-class1-reference"),
                              (np.array([[12]], dtype=np.uint8), "class-1-only"),
                              (np.array([[1]], dtype=np.int32), "class-1-only"),
                              (np.array([1], dtype=np.uint8), "class-1-only"),
                              (np.array([[1]], dtype=np.uint8), "unknown")):
            with self.subTest(scope=scope, pixels=pixels), self.assertRaises(ValueError):
                binary_labels(pixels, scope)

    def test_binary_reference_preferred_over_newer_partial(self):
        binary = self.candidate([[0, 1]], "binary-class1-reference")
        partial = {**binary, "scope": "class-1-only", "timestamp": "2026-11-19T00:00:00Z",
                   "pixel_counts": {"1": 1, "255": 1}}
        self.assertIs(select_candidate(self.row(partial, binary)), binary)

    def test_latest_and_tie_break_selection_order_independent(self):
        old = self.candidate([[1, 255]])
        new = {**old, "timestamp": "2026-11-19T00:00:00Z"}
        self.assertIs(select_candidate(self.row(new, old)), new)
        self.assertIs(select_candidate(self.row(old, new)), new)
        tied = {**new, "mask_identity": new["mask_identity"] + "z"}
        self.assertIs(select_candidate(self.row(tied, new)), tied)
        self.assertIs(select_candidate(self.row(new, tied)), tied)

    def test_all_ignore_does_not_displace_usable_version(self):
        good = self.candidate([[1, 255]])
        empty = {**good, "timestamp": "2026-11-19T00:00:00Z", "pixel_counts": {"255": 2}}
        self.assertIs(select_candidate(self.row(good, empty)), good)

    def test_unaccepted_or_wrong_source_candidate_rejected(self):
        good = self.candidate([[1, 255]])
        for change in ({"decision": "needs_correction"}, {"decision": "unreviewed"},
                       {"source_sha256": "wrong"}, {"timestamp": "2026-11-19T00:00:00"}):
            row = self.row(good, {**good, **change})
            with self.subTest(change=change), self.assertRaises(ValueError):
                select_candidate(row)

    def test_reviewed_rle_decoded_exactly(self):
        candidate = self.candidate([[0, 1, 255]], correction=True)
        pixels = candidate_pixels(candidate, Inputs(self.output))
        np.testing.assert_array_equal(pixels, [[0, 1, 255]])

    def test_rle_draft_wrong_identity_or_invalid_runs_rejected(self):
        candidate = self.candidate([[0, 1, 255]], correction=True)
        path = Path(candidate["evidence_path"])
        original = json.loads(path.read_text())
        for change in ({"status": "draft"}, {"source_sha256": "wrong"},
                       {"pixels_rle": [0, 0]}, {"pixels_sha256": "wrong"}, {"size": [1, 3]}):
            value = copy.deepcopy(original)
            value["entries"][0].update(change)
            path.write_text(json.dumps(value))
            modified = {**candidate, "evidence_sha256": sha256(path)}
            with self.subTest(change=change), self.assertRaises(ValueError):
                candidate_pixels(modified, Inputs(self.output))

    def test_source_mask_evidence_or_counts_tampering_rejected(self):
        for field in ("source_path", "mask_path", "evidence_path", "pixel_counts"):
            candidate = self.candidate([[1, 255]])
            if field == "pixel_counts":
                candidate[field] = {"1": 2}
            else:
                with Path(candidate[field]).open("ab") as handle:
                    handle.write(b"tamper")
            with self.subTest(field=field), self.assertRaises(ValueError):
                candidate_pixels(candidate, Inputs(self.output))

    def test_export_and_receipt_preserve_originals_and_exclude_empty(self):
        candidates = [self.candidate([[0, 1, 255]], correction=True), self.candidate([[1, 255, 255]]),
                      self.candidate([[1, 2, 0]]), self.candidate([[255, 255, 255]])]
        path = self.inventory([self.row(candidate) for candidate in candidates])
        before = {p: sha256(p) for p in self.inputs.iterdir() if p.is_file()}
        summary = prepare(path, self.output)
        self.assertEqual(summary["usable_images"], 3)
        self.assertEqual(summary["excluded_all_ignore"], 1)
        self.assertEqual(summary["supervision"], {"binary-reference": 1, "sidewalk-positive-only": 2})
        self.assertEqual(summary["binary_references_with_ignore"], 1)
        self.assertEqual(len(list((self.output / "images").iterdir())), 3)
        self.assertEqual(len(list((self.output / "excluded/images").iterdir())), 1)
        self.assertEqual(before, {p: sha256(p) for p in before})
        self.assertEqual(verify_dataset(self.output), summary)
        # Verification must work even when the original evidence is unavailable.
        self.inputs.rename(self.root / "archived-inputs")
        self.assertEqual(verify_dataset(self.output), summary)

    def test_duplicate_images_and_existing_output_rejected(self):
        candidate = self.candidate([[1, 255]])
        row = self.row(candidate)
        with self.assertRaises(ValueError):
            prepare(self.inventory([row, row]), self.output)
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("keep")
        with self.assertRaises(FileExistsError):
            prepare(self.inventory([row]), self.output)
        self.assertEqual(marker.read_text(), "keep")

    def test_failed_export_does_not_publish_or_leave_staging_files(self):
        candidate = self.candidate([[1, 255]])
        candidate["pixels_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            prepare(self.inventory([self.row(candidate)]), self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob("*.building-*")))

    def test_output_tampering_is_detected(self):
        candidate = self.candidate([[0, 1]], "binary-class1-reference")
        prepare(self.inventory([self.row(candidate)]), self.output)
        mask = next((self.output / "masks").iterdir())
        Image.fromarray(np.array([[1, 1]], dtype=np.uint8)).save(mask)
        with self.assertRaises(ValueError):
            verify_dataset(self.output)


if __name__ == "__main__":
    unittest.main()
