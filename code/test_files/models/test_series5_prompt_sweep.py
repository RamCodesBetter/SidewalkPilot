#!/usr/bin/env python3
"""Guard the matched six-recipe comparison contract without loading a model."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))

from compare_class1_methods import aggregate
from compare_sam31_sidewalk import COMMIT, CHECKPOINT_SHA256, SAM3_CHECKPOINT_SHA256
from evaluate_sam_prompt_sweep import validate_configs
from run_sam_prompt_sweep import PROMPTS, THRESHOLD


class PromptSweepTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"status": "complete", "score_threshold": THRESHOLD,
                     "selection_sha256": "selection", "runner_sha256": "runner", "recipes": []}
        self.configs = {}
        for model in ("sam3", "sam31"):
            control = model == "sam3"
            for index, prompt in enumerate(PROMPTS, 1):
                key = f"{model}-p{index}"
                self.plan["recipes"].append({"key": key, "prompt": prompt})
                self.configs[key] = {
                    "prompt": prompt, "score_threshold": THRESHOLD, "mask_threshold": .5,
                    "model": "facebook/sam3" if control else "facebook/sam3.1",
                    "checkpoint_sha256": SAM3_CHECKPOINT_SHA256 if control else CHECKPOINT_SHA256,
                    "native_sam3_control": control, "official_source_commit": COMMIT,
                    "selection_sha256": "selection", "runner_sha256": "runner",
                    "weight_dtype": "float32", "autocast": "bfloat16", "tf32": False,
                    "use_fa3": False, "use_rope_real": False, "packages": {},
                    "sam3_config_sha256": "processor", "official_file_sha256": {},
                    "supervise_joint_box_scores": not control,
                    "load_report": {"strict": True, "missing_detector_keys": [], "unexpected_detector_keys": []}}

    def test_complete_matched_sweep_passes(self):
        validate_configs(self.plan, self.configs, "selection")

    def test_incomplete_or_reordered_sweep_rejected(self):
        for change in ("status", "missing", "order"):
            plan, configs = deepcopy(self.plan), deepcopy(self.configs)
            if change == "status":
                plan["status"] = "running"
            elif change == "missing":
                del configs["sam31-p3"]
            else:
                plan["recipes"].reverse()
            with self.assertRaises(ValueError):
                validate_configs(plan, configs, "selection")

    def test_prompt_threshold_or_runtime_mismatch_rejected(self):
        changes = {"prompt": "pavement", "score_threshold": .5, "autocast": False,
                   "packages": {"torch": "other"}, "sam3_config_sha256": "other",
                   "selection_sha256": "other", "runner_sha256": "other"}
        for field, value in changes.items():
            with self.subTest(field=field):
                configs = deepcopy(self.configs)
                configs["sam31-p3"][field] = value
                with self.assertRaises(ValueError):
                    validate_configs(self.plan, configs, "selection")

    def test_wrong_checkpoint_or_double_presence_policy_rejected(self):
        for field, value in (("checkpoint_sha256", SAM3_CHECKPOINT_SHA256),
                             ("supervise_joint_box_scores", False),
                             ("load_report", {"strict": False, "missing_detector_keys": [], "unexpected_detector_keys": []})):
            configs = deepcopy(self.configs)
            configs["sam31-p1"][field] = value
            with self.assertRaises(ValueError):
                validate_configs(self.plan, configs, "selection")

    def test_zero_detection_failures_stay_in_mean(self):
        perfect = {"tp": 10, "fp": 0, "fn": 0, "tn": 10, "ignored": 0, "iou": 1.}
        empty = {"tp": 0, "fp": 0, "fn": 10, "tn": 10, "ignored": 0, "iou": 0.}
        result = aggregate([{"metrics": {"method": score}} for score in (perfect, empty)])
        self.assertEqual(result["method"]["macro_iou"], .5)
        self.assertEqual(result["method"]["images"], 2)


if __name__ == "__main__":
    unittest.main()
