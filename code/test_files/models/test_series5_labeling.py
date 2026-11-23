#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2] / "ai_models_datasets" / "series_5" / "tools"
sys.path.insert(0, str(ROOT))
from workspace import activate, source_path
activate()
import package_review
import diagnose_reviews
import sam_point_diagnostic
import label_assisted_pilot
import prepare_assisted_pilot
import audit_sam_implementations as sam_audit
import compare_sam3_sidewalk as sam3_compare
SPEC = importlib.util.spec_from_file_location("label_grounded_sam2", source_path('label_grounded_sam2.py'))
label = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(label)
REVIEW_SPEC = importlib.util.spec_from_file_location("review_masks", source_path('review_masks.py'))
review = importlib.util.module_from_spec(REVIEW_SPEC)
REVIEW_SPEC.loader.exec_module(review)
TAXONOMY = json.loads((source_path('taxonomy.json')).read_text())


class LabelingTests(unittest.TestCase):
    def test_sam3_union_handles_no_detections_and_keeps_all_instances(self):
        np.testing.assert_array_equal(sam3_compare.union_instances(np.zeros((0, 2, 3), bool), (2, 3)),
                                      np.zeros((2, 3), bool))
        np.testing.assert_array_equal(sam3_compare.union_instances(np.zeros((0, 4, 4), bool), (2, 3)),
                                      np.zeros((2, 3), bool))
        masks = np.array([[[1, 0], [0, 0]], [[0, 0], [0, 1]]], dtype=bool)
        np.testing.assert_array_equal(sam3_compare.union_instances(masks, (2, 2)), [[1, 0], [0, 1]])

    def test_sam3_masks_reject_wrong_dimensions_and_nonbinary_values(self):
        for value in (np.zeros((2, 3)), np.ones((1, 2, 2)), np.full((2, 2), 255), np.full((2, 2), np.nan)):
            with self.assertRaises(ValueError):
                sam3_compare.binary_mask(value, (2, 2))
        for value in (np.zeros((2, 2)), np.zeros((1, 2, 3)), np.full((1, 2, 2), .5)):
            with self.assertRaises(ValueError):
                sam3_compare.union_instances(value, (2, 2))

    def test_sam3_output_cannot_replace_or_enter_baseline_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            baseline.mkdir()
            for output in (root, baseline, baseline / "child"):
                with self.assertRaises(ValueError):
                    sam3_compare.output_path(output, [baseline])
            self.assertEqual(sam3_compare.output_path(root / "new", [baseline]), root / "new")

    def test_sam3_saved_masks_use_ignore_not_background(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "masks").mkdir()
            result = sam3_compare.save_binary(root, "example", np.array([[True, False]]))
            with Image.open(root / result["path"]) as handle:
                np.testing.assert_array_equal(np.asarray(handle), [[1, 255]])
            self.assertEqual(result["review_status"], "unreviewed")
            self.assertEqual(result["class_1_pixels"], 1)
            self.assertEqual(result["sha256"], label.sha256(root / result["path"]))

    def test_audit_agreement_distinguishes_empty_and_different_masks(self):
        empty = np.zeros((2, 2), dtype=bool)
        self.assertEqual(sam_audit.agreement(empty, empty),
                         {"iou": None, "different_pixels": 0, "total_pixels": 4})
        a = np.array([[1, 0], [0, 0]], dtype=bool)
        b = np.array([[1, 1], [0, 0]], dtype=bool)
        self.assertEqual(sam_audit.agreement(a, b),
                         {"iou": .5, "different_pixels": 1, "total_pixels": 4})
        self.assertEqual(sam_audit.agreement(a, a)["iou"], 1)

    def test_audit_agreement_rejects_broadcasting(self):
        for a, b in ((np.zeros((2, 2)), np.zeros((2, 1))),
                     (np.zeros(2), np.zeros(2)),
                     (np.zeros((1, 2, 2)), np.zeros((1, 2, 2)))):
            with self.assertRaises(ValueError):
                sam_audit.agreement(a, b)

    def test_audit_gate_rejection_does_not_mean_empty_raw_prediction(self):
        masks = np.array([[[1, 1]], [[1, 0]]], dtype=bool)
        gated, detail = sam_audit.selected_pixels(masks, [.99, .69], [[0, 0], [1, 0]], [1, 0])
        self.assertFalse(gated.any())
        self.assertIsNone(detail["selected"])
        self.assertEqual(detail["raw_best"], 0)
        self.assertEqual(detail["point_consistent"], [False, True])
        self.assertTrue(masks[0].any())
        gated, detail = sam_audit.selected_pixels(masks, [.99, .7], [[0, 0], [1, 0]], [1, 0])
        self.assertEqual(detail["selected"], 1)
        np.testing.assert_array_equal(gated, masks[1])

    def test_audit_saves_raw_candidates_even_when_gate_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "masks").mkdir()
            (root / "logits").mkdir()
            masks = np.array([[[1, 1]]], dtype=bool)
            logits = np.ones((1, 1, 2), dtype=np.float32)
            _, detail = sam_audit.save_variant(root, "test", masks, [.99], [[0, 0], [1, 0]], [1, 0], logits)
            self.assertIsNone(detail["selected"])
            self.assertEqual(detail["class_1_pixels"], 0)
            with Image.open(root / detail["masks"][0]["path"]) as handle:
                np.testing.assert_array_equal(np.asarray(handle), [[1, 1]])
            self.assertEqual(label.sha256(root / detail["masks"][0]["path"]), detail["masks"][0]["sha256"])
            with np.load(root / detail["low_res_logits"]) as saved:
                np.testing.assert_array_equal(saved["logits"], logits)

    def test_audit_selection_has_ten_unique_fixed_frames(self):
        self.assertEqual(sam_audit.INDICES, (1, 3, 4, 7, 10, 11, 14, 16, 18, 19))
        self.assertEqual(len(sam_audit.REASONS), 10)
        self.assertEqual(len(set(sam_audit.INDICES)), 10)

    def test_refinement_seed_prefers_point_agreement_over_quality(self):
        masks = np.array([[[1, 1]], [[1, 0]], [[1, 0]]], dtype=bool)
        seed, violations = label_assisted_pilot.refinement_seed(masks, [.99, .8, .9], [[0, 0], [1, 0]], [1, 0])
        self.assertEqual(seed, 2)
        self.assertEqual(violations, [1, 0, 0])
        seed, _ = label_assisted_pilot.refinement_seed(masks, [float('nan')]*3, [[0, 0]], [1])
        self.assertIsNone(seed)
        with self.assertRaises(ValueError):
            label_assisted_pilot.refinement_seed(masks, [.5], [[0, 0]], [1])

    def test_fresh_selection_is_balanced_reproducible_and_spaced(self):
        names = [f"run_{r}__photo_20261025_1200{s:02d}_000000.jpg" for r in range(5) for s in range(60)]
        excluded = [n for n in names if "120030" in n]
        selected = prepare_assisted_pilot.fresh_selection(names, excluded, per_run=5)
        self.assertEqual(selected, prepare_assisted_pilot.fresh_selection(list(reversed(names)), excluded, per_run=5))
        self.assertEqual(len(set(selected)), 25)
        for run in range(5):
            group = [n for n in selected if n.startswith(f"run_{run}__")]
            self.assertEqual(len(group), 5)
            times = sorted(prepare_assisted_pilot.frame_time(n) for n in group)
            self.assertTrue(all(b - a > 2 for a, b in zip(times, times[1:])))
            old = prepare_assisted_pilot.frame_time(excluded[run])
            self.assertTrue(all(abs(t - old) > 2 for t in times))
        with self.assertRaises(ValueError):
            prepare_assisted_pilot.fresh_selection(names[:2], [], per_run=40)
        with self.assertRaises(ValueError):
            prepare_assisted_pilot.fresh_selection(names, [], per_run=0)

    def test_annotation_batches_require_complete_unique_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = {"p": [[500, 800]], "n": [[0, 0]]}
            (root / "annotations-a.json").write_text(json.dumps({"1": a}))
            self.assertEqual(label_assisted_pilot.load_annotations(root, 1), {"1": a})
            with self.assertRaises(ValueError):
                label_assisted_pilot.load_annotations(root, 2)
            (root / "annotations-b.json").write_text(json.dumps({"1": a}))
            with self.assertRaises(ValueError):
                label_assisted_pilot.load_annotations(root, 1)
            (root / "annotations-a.json").write_text('{"1": {}, "1": {}}')
            with self.assertRaises(ValueError):
                label_assisted_pilot.load_annotations(root, 1)

    def test_normalized_points_and_explicit_abstentions(self):
        self.assertEqual(label_assisted_pilot.pixel_prompt({"p": [[1000, 1000]], "n": [[0, 0]]}, 1280, 720),
                         {"positive": [[1279, 719]], "negative": [[0, 0]]})
        self.assertIsNone(label_assisted_pilot.pixel_prompt({"abstain": "Blurred"}, 1280, 720))
        for bad in ({"abstain": ""}, {"abstain": "Blurred", "p": [[1, 1]]},
                    {"p": [[1001, 500]], "n": [[0, 0]]}, {"p": [[True, 500]], "n": [[0, 0]]},
                    {"p": [[1, 1]], "n": [[0, 0]]}, {"p": [], "n": [[0, 0]]},
                    {"p": [[500, 500]], "n": [[0, 0]], "tags": "not a list"}):
            with self.assertRaises(ValueError):
                label_assisted_pilot.pixel_prompt(bad, 10, 10)

    def test_assisted_source_validation_rejects_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frame.jpg").write_bytes(b"source fixture")
            (root / "labels.json").write_text('{"frame.jpg": {}}')
            selection = {"source": str(root), "images": ["frame.jpg"], "source_count": 1,
                         "source_names_sha256": label.digest_json(["frame.jpg"]),
                         "steering_labels_sha256": label.sha256(root / "labels.json"),
                         "source_sha256": {"frame.jpg": label.sha256(root / "frame.jpg")}}
            self.assertEqual(label_assisted_pilot.validate_sources(selection), (root, ["frame.jpg"]))
            selection["excluded_names"] = ["frame.jpg"]
            with self.assertRaises(ValueError):
                label_assisted_pilot.validate_sources(selection)
            selection["excluded_names"] = []
            (root / "frame.jpg").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                label_assisted_pilot.validate_sources(selection)

    def test_shadow_repair_is_bounded_additive_and_sam_supported(self):
        before = np.full((5, 5), 255, dtype=np.uint8)
        before[0, 0] = before[2, 2] = 1
        candidate = np.ones((5, 5), dtype=np.uint8)
        candidate[2, 2] = candidate[3, 3] = 255
        repaired, additions = sam_point_diagnostic.restrict_shadow_additions(before, candidate, [[[1, 1], [3, 1], [3, 3], [1, 3]]])
        self.assertEqual(additions, 7)
        self.assertEqual(repaired[2, 2], 1, "Never remove previously accepted sidewalk")
        self.assertEqual(repaired[3, 3], 255, "Do not fill holes without SAM support")
        np.testing.assert_array_equal(repaired[0], before[0])
        np.testing.assert_array_equal(repaired[4], before[4])
        np.testing.assert_array_equal(repaired[:, 0], before[:, 0])
        np.testing.assert_array_equal(repaired[:, 4], before[:, 4])

    def test_shadow_repair_rejects_invalid_regions_and_class_ids(self):
        mask = np.ones((5, 5), dtype=np.uint8)
        for polygons in ([], [[[0, 0], [1, 1]]], [[[0, 0], [5, 0], [0, 4]]], [[[0, 0], [4.0, 0], [0, 4]]]):
            with self.assertRaises(ValueError):
                sam_point_diagnostic.restrict_shadow_additions(mask, mask, polygons)
        other_class = mask.copy(); other_class[2, 2] = 5
        with self.assertRaises(ValueError):
            sam_point_diagnostic.restrict_shadow_additions(other_class, mask, [[[0, 0], [4, 0], [0, 4]]])

    def test_point_prompts_require_valid_original_coordinates(self):
        self.assertEqual(sam_point_diagnostic.validate_points({"positive": [[0, 0]], "negative": [[9, 7]]}, 10, 8),
                         ([[0, 0], [9, 7]], [1, 0]))
        for bad in ([[10, 0]], [[0, 8]], [[-1, 0]], [[.5, 0]], [[True, 0]], [[0]], []):
            with self.assertRaises(ValueError):
                sam_point_diagnostic.validate_points({"positive": bad, "negative": [[9, 7]]}, 10, 8)
        with self.assertRaises(ValueError):
            sam_point_diagnostic.validate_points({"positive": [[0, 0]], "negative": [[0, 0]]}, 10, 8)

    def test_point_choice_requires_every_point_and_quality(self):
        masks = np.array([[[1, 0]], [[1, 1]], [[1, 0]]], dtype=bool)
        selected, consistent = sam_point_diagnostic.choose_mask(masks, [.8, .99, .9], [[0, 0], [1, 0]], [1, 0])
        self.assertEqual(selected, 2)
        self.assertEqual(consistent, [True, False, True])
        selected, _ = sam_point_diagnostic.choose_mask(masks, [.69, .99, float("nan")], [[0, 0], [1, 0]], [1, 0])
        self.assertIsNone(selected)

    def test_taxonomy_ids_and_prompts(self):
        label.validate_taxonomy(TAXONOMY)

    def test_sampling_reproducible_unique_and_proportional(self):
        names = [f"run_a__{i:04d}.jpg" for i in range(300)] + [f"run_b__{i:04d}.jpg" for i in range(100)]
        selected = label.select_pilot(names, 200, 42)
        self.assertEqual(selected, label.select_pilot(list(reversed(names)), 200, 42))
        self.assertEqual(len(set(selected)), 200)
        self.assertEqual(sum(n.startswith("run_a") for n in selected), 150)
        self.assertNotEqual(selected, label.select_pilot(names, 200, 43))

    def test_invalid_sample_count(self):
        for count in (0, 3):
            with self.assertRaises(ValueError):
                label.select_pilot(["a.jpg", "b.jpg"], count, 1)

    def test_explicit_diagnostic_selection(self):
        self.assertEqual(label.validate_selection({"images": ["b.jpg", "a.jpg"]}, ["a.jpg", "b.jpg", "c.jpg"], 2), ["b.jpg", "a.jpg"])
        for images in (["a.jpg", "a.jpg"], ["unknown.jpg", "a.jpg"], ["a.jpg"], [1, "a.jpg"], "a.jpg"):
            with self.assertRaises(ValueError):
                label.validate_selection({"images": images}, ["a.jpg", "b.jpg"], 2)

    def test_diagnostic_set_covers_failures_and_approved_controls(self):
        rows = [{"image": f"{r}__{i}.jpg", "run": r, "decision": "correct" if i == 4 else "needs_correction", "class_1_fraction": i / 5}
                for r in ("run_a", "run_b") for i in range(5)]
        selected = diagnose_reviews.select_diagnostics(rows)
        self.assertEqual(len(selected), 8)
        self.assertEqual(len({r["image"] for r in selected}), 8)
        self.assertEqual(sum(r["decision"] == "correct" for r in selected), 2)
        self.assertEqual(selected, diagnose_reviews.select_diagnostics(list(reversed(rows))))
        with self.assertRaises(ValueError):
            diagnose_reviews.select_diagnostics(rows[:2])

    def test_ambiguous_phrases_not_guessed(self):
        classes = TAXONOMY["classes"]
        self.assertEqual(label.map_phrase("grass . gravel", classes), 3)
        self.assertEqual(label.map_phrase("raised curb", classes), 10)
        self.assertIsNone(label.map_phrase("sidewalk road", classes))
        self.assertIsNone(label.map_phrase("carpet", classes))
        self.assertIsNone(label.map_phrase("unrecognized", classes))

    def test_prompt_scores_keep_distinct_class_alternatives(self):
        classes = [{"id":1,"prompts":["sidewalk"]},{"id":2,"prompts":["road"]}]
        caption, spans = label.build_caption(classes)
        self.assertEqual(caption, "sidewalk. road.")
        probabilities = np.array([[.99, .8, .1, .6, .1, .99]])
        scores, ids, phrases = label.score_prompt_spans(probabilities, [(0,0),(0,8),(8,9),(10,14),(14,15),(0,0)], spans)
        np.testing.assert_allclose(scores, [[.8,.6]])
        self.assertEqual(ids,[1,2])
        self.assertEqual(phrases,["sidewalk","road"])

    def test_prompt_scores_average_wordpieces_not_punctuation(self):
        scores, _, _ = label.score_prompt_spans(np.array([[.8,.4,.99]]), [(0,3),(3,5),(5,6)], [(3,"mulch",0,5)])
        np.testing.assert_allclose(scores, [[.6]])

    def test_empty_scene_is_ignore_not_background(self):
        np.testing.assert_array_equal(label.compose_mask([], (3, 4), TAXONOMY, .05), np.full((3, 4), 255))

    def test_conflicting_surfaces_mark_ignore(self):
        pixels = np.ones((2, 2), dtype=bool)
        mask = label.compose_mask([(1, pixels, .8), (2, pixels, .78)], (2, 2), TAXONOMY, .05)
        self.assertTrue(np.all(mask == 255))

    def test_weak_foreground_does_not_override_stronger_surface(self):
        surface = np.ones((2, 2), dtype=bool)
        person = np.array([[True, False], [False, False]])
        mask = label.compose_mask([(1, surface, .9), (5, person, .4)], (2, 2), TAXONOMY, .05)
        np.testing.assert_array_equal(mask, [[1, 1], [1, 1]])

    def test_stronger_foreground_is_kept(self):
        surface = np.ones((2, 2), dtype=bool)
        person = np.array([[True, False], [False, False]])
        mask = label.compose_mask([(1, surface, .5), (5, person, .9)], (2, 2), TAXONOMY, .05)
        np.testing.assert_array_equal(mask, [[5, 1], [1, 1]])

    def test_cross_layer_conflict_is_uncertain(self):
        pixels = np.ones((2, 2), dtype=bool)
        mask = label.compose_mask([(1, pixels, .5), (10, pixels, .48)], (2, 2), TAXONOMY, .05)
        self.assertTrue(np.all(mask == 255))

    def test_same_class_overlaps_do_not_become_ignore(self):
        pixels = np.ones((2, 2), dtype=bool)
        mask = label.compose_mask([(1, pixels, .8), (1, pixels, .79)], (2, 2), TAXONOMY, .05)
        self.assertTrue(np.all(mask == 1))

    def test_png_preserves_exact_ids_and_overlay_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mask = np.array([[0, 1, 11, 255]], dtype=np.uint8)
            label.save_mask(root / "mask.png", mask)
            with Image.open(root / "mask.png") as saved:
                np.testing.assert_array_equal(np.asarray(saved), mask)
            label.save_overlay(root / "overlay.jpg", Image.new("RGB", (4, 1)), mask, TAXONOMY)
            with Image.open(root / "overlay.jpg") as overlay:
                self.assertEqual(overlay.size, (8, 33))

    def test_review_server_blocks_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inside.txt").write_text("test")
            self.assertEqual(review.resolve_file(root, "inside.txt"), root / "inside.txt")
            with self.assertRaises(FileNotFoundError):
                review.resolve_file(root, "../outside.txt")
            with self.assertRaises(FileNotFoundError):
                review.resolve_file(root, "%2Fetc%2Fpasswd")

    def test_existing_record_checks_output_and_source_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("source.jpg", "mask.png", "overlay.jpg"):
                (root / name).write_bytes(b"test")
            record = {"image":"source.jpg", "source_sha256":label.sha256(root / "source.jpg"),
                      "mask":"mask.png", "mask_sha256":label.sha256(root / "mask.png"),
                      "overlay":"overlay.jpg", "overlay_sha256":label.sha256(root / "overlay.jpg")}
            label.verify_record(root, record, root)
            (root / "source.jpg").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                label.verify_record(root, record, root)

    def test_portable_package_contains_only_verified_selected_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, source = root / "pilot", root / "source"
            dataset.mkdir()
            source.mkdir()
            (dataset / "records").mkdir()
            (dataset / "masks").mkdir()
            (dataset / "overlays").mkdir()
            Image.new("RGB", (8, 8)).save(source / "image.jpg")
            Image.new("L", (8, 8), 255).save(dataset / "masks/image.png")
            Image.new("RGB", (16, 40)).save(dataset / "overlays/image.jpg")
            record = {"image":"image.jpg","source_sha256":label.sha256(source/"image.jpg"),
                      "mask":"masks/image.png","mask_sha256":label.sha256(dataset/"masks/image.png"),
                      "overlay":"overlays/image.jpg","overlay_sha256":label.sha256(dataset/"overlays/image.jpg")}
            label.write_json(dataset / "records/image.json", record)
            (dataset / "label_grounded_sam2.py").write_text("# fixture\n")
            label.write_json(dataset / "manifest.json", {"images":["image.jpg"],"contract":{
                "source":str(source),"source_count":1,"runner_sha256":label.sha256(dataset/"label_grounded_sam2.py")}})
            for name in ("taxonomy.json","label_config.json","summary.json"):
                label.write_json(dataset/name,{})
            result = package_review.package(dataset, root / "review.tar")
            self.assertEqual(result["images"],1)
            with tarfile.open(root / "review.tar") as archive:
                information = json.load(archive.extractfile("pilot/package.json"))
                self.assertFalse(information["full_dataset"])
                self.assertTrue(information["human_review_required"])
                self.assertEqual(information["count"],1)
                self.assertIn("pilot/images/image.jpg",archive.getnames())
                self.assertIn("pilot/review_masks.py",archive.getnames())
                self.assertTrue(all(m.isfile() and m.uid == 0 and m.gid == 0 for m in archive.getmembers()))
            with self.assertRaises(FileExistsError):
                package_review.package(dataset, root / "review.tar")
            # Diagnostic archives retain the alternate runner, point selection, and helpers.
            (dataset / "point_runner.py").write_text("# alternate runner fixture\n")
            (dataset / "selection.json").write_text('{"images": ["image.jpg"]}\n')
            manifest = json.loads((dataset / "manifest.json").read_text())
            manifest["contract"].update({"runner_file": "point_runner.py", "runner_sha256": label.sha256(dataset/"point_runner.py"),
                                         "helper_files_sha256": {"label_grounded_sam2.py": label.sha256(dataset/"label_grounded_sam2.py")},
                                         "selection_sha256": label.sha256(dataset/"selection.json")})
            label.write_json(dataset / "manifest.json", manifest)
            package_review.package(dataset, root / "diagnostic.tar")
            with tarfile.open(root / "diagnostic.tar") as archive:
                self.assertIn("pilot/selection.json", archive.getnames())
                self.assertIn("pilot/point_runner.py", archive.getnames())
                self.assertIn("pilot/label_grounded_sam2.py", archive.getnames())
            (dataset / "Before-after").mkdir()
            label.write_json(dataset / "Before-after/comparison.json", {"images": [{"image": "image.jpg"}]})
            Image.new("RGB", (24, 8)).save(dataset / "Before-after/01.jpg")
            Image.new("RGB", (24, 8)).save(dataset / "Before-after/sheet-1.jpg")
            package_review.package(dataset, root / "comparison.tar")
            with tarfile.open(root / "comparison.tar") as archive:
                info = json.load(archive.extractfile("pilot/package.json"))
                for name in ("comparison.json", "01.jpg", "sheet-1.jpg"):
                    self.assertIn("pilot/Before-after/" + name, archive.getnames())
                    self.assertEqual(info["files_sha256"]["Before-after/" + name],
                                     label.sha256(dataset / "Before-after" / name))
            label.write_json(dataset / "Before-after/comparison.json", {"images": [{"image": "different.jpg"}]})
            with self.assertRaisesRegex(ValueError, "ordered package images"):
                package_review.package(dataset, root / "mismatch.tar")
            label.write_json(dataset / "Before-after/comparison.json", {"images": [{"image": "image.jpg"}]})
            (dataset / "Before-after/01.jpg").rename(dataset / "Before-after/missing.jpg")
            with self.assertRaisesRegex(ValueError, "missing file"):
                package_review.package(dataset, root / "missing.tar")
            (dataset / "Before-after/missing.jpg").rename(dataset / "Before-after/01.jpg")
            for name in ("point_runner.py", "label_grounded_sam2.py", "selection.json"):
                original = (dataset / name).read_bytes()
                (dataset / name).write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    package_review.package(dataset, root / "tampered.tar")
                self.assertFalse((root / "tampered.tar").exists())
                (dataset / name).write_bytes(original)
            (dataset / "masks/image.png").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                package_review.package(dataset, root / "bad.tar")
            self.assertFalse((root / "bad.tar").exists())

    def test_package_member_rejects_escape_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("/etc/passwd", "../outside", "..\\outside"):
                with self.assertRaises(ValueError):
                    package_review.safe_member(Path(directory), name)


if __name__ == "__main__":
    unittest.main()
