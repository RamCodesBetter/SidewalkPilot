#!/usr/bin/env python3
"""Check the isolated SAM 3 postprocessor API without downloading model weights."""

import argparse
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--runtime", type=Path, required=True)
args, remaining = parser.parse_known_args()
sys.path.insert(0, str(args.runtime.resolve()))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets" / "series_5" / "tools"))
from workspace import activate
activate()

import numpy as np
import torch
import transformers
from transformers import Sam3ImageProcessor
from compare_sam3_sidewalk import TRANSFORMERS_VERSION, binary_mask, union_instances
from compare_sam31_sidewalk import detector_state, hf_outputs, validate_prompt_settings


class Sam3RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(transformers.__version__, TRANSFORMERS_VERSION)
        self.processor = Sam3ImageProcessor()
        self.outputs = SimpleNamespace(
            pred_logits=torch.tensor([[10., -10.]]),
            presence_logits=torch.tensor([[10.]]),
            pred_boxes=torch.tensor([[[.25, .25, .75, .75], [0., 0., 1., 1.]]]),
            pred_masks=torch.full((1, 2, 2, 2), 10.),
            semantic_seg=torch.tensor([[[[10., -10.], [10., -10.]]]]),
        )

    def instances(self):
        return self.processor.post_process_instance_segmentation(
            self.outputs, threshold=.5, mask_threshold=.5, target_sizes=[(4, 6)],
        )[0]

    def test_score_filter_resize_and_box_coordinates(self):
        result = self.instances()
        self.assertEqual(tuple(result["masks"].shape), (1, 4, 6))
        self.assertTrue(union_instances(result["masks"].numpy(), (4, 6)).all())
        torch.testing.assert_close(result["boxes"], torch.tensor([[1.5, 1., 4.5, 3.]]))
        expected = torch.sigmoid(torch.tensor(10.)) ** 2
        torch.testing.assert_close(result["scores"], expected.reshape(1))

    def test_empty_instances_yield_original_size_empty_union(self):
        self.outputs.presence_logits.fill_(-10.)
        result = self.instances()
        self.assertEqual(len(result["masks"]), 0)
        np.testing.assert_array_equal(
            union_instances(result["masks"].numpy(), (4, 6)), np.zeros((4, 6), bool),
        )

    def test_semantic_head_is_separate_from_presence_gate(self):
        self.outputs.presence_logits.fill_(-10.)
        mask = self.processor.post_process_semantic_segmentation(
            self.outputs, threshold=.5, target_sizes=[(4, 6)],
        )[0]
        actual = binary_mask(mask.numpy(), (4, 6))
        expected = np.zeros((4, 6), bool)
        expected[:, :3] = True
        np.testing.assert_array_equal(actual, expected)

    def test_sam31_joint_confidence_is_not_multiplied_twice(self):
        raw = {"pred_logits": torch.logit(torch.tensor([[[.6]]])),
               "presence_logit_dec": torch.logit(torch.tensor([[.7]])),
               "pred_masks": torch.full((1, 1, 2, 2), 10.),
               "pred_boxes": torch.tensor([[[.5, .5, .5, .5]]])}
        out = hf_outputs(raw, joint_scores=True)
        self.assertIsNone(out.presence_logits)
        torch.testing.assert_close(out.pred_boxes, torch.tensor([[[.25, .25, .75, .75]]]))
        result = self.processor.post_process_instance_segmentation(out, threshold=.5, target_sizes=[(4, 6)])[0]
        torch.testing.assert_close(result["scores"], torch.tensor([.6]))
        self.assertEqual(tuple(result["masks"].shape), (1, 4, 6))
        independent = hf_outputs(raw, joint_scores=False)
        result = self.processor.post_process_instance_segmentation(independent, threshold=.5, target_sizes=[(4, 6)])[0]
        self.assertEqual(len(result["masks"]), 0)

    def test_sam31_adapter_rejects_ambiguous_shape_or_policy(self):
        with self.assertRaises(ValueError):
            hf_outputs({"pred_logits": torch.ones((1, 2))}, joint_scores=True)
        with self.assertRaises(ValueError):
            hf_outputs({"pred_logits": torch.ones((1, 2, 1))}, joint_scores=None)

    def test_sam31_strict_detector_namespace(self):
        value = {"detector.a": torch.ones(2), "tracker.b": torch.zeros(2)}
        selected, unused = detector_state({"model": value})
        self.assertEqual(set(selected), {"a"})
        self.assertEqual(unused, 1)
        for invalid in ({}, {"tracker.a": 1}, {"other.a": 1}):
            with self.assertRaises(ValueError):
                detector_state(invalid)

    def test_prompt_settings_preserve_defaults_and_reject_invalid_values(self):
        for prompt in ("sidewalk", "sidewalk pavement", "concrete sidewalk"):
            for threshold in (.4, .5):
                validate_prompt_settings(prompt, threshold)
        for prompt in (None, "", " ", " sidewalk", "sidewalk "):
            with self.assertRaises(ValueError):
                validate_prompt_settings(prompt, .4)
        for threshold in (0, 1, -.1, 1.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                validate_prompt_settings("sidewalk", threshold)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *remaining])
