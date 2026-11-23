"""Numerical and supervision-contract checks; no dataset or model downloads."""
import math
from pathlib import Path
import sys
import unittest

import torch

SERIES5 = Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"
sys.path.insert(0, str(SERIES5))
sys.path.insert(0, str(SERIES5 / "tools"))
from workspace import activate
activate()
from segmentation_losses import ReviewedFocalLoss
from series_5_b_sidewalkpilot_trainer import conservative_loss


class FocalLossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def fixture(self):
        logits = torch.tensor([[[[0., 0., 4.]], [[math.log(4), math.log(4), -1.]]]], requires_grad=True)
        return logits, torch.tensor([[[0, 1, 255]]]), torch.tensor([True])

    def test_hand_calculated_focal_and_class_weights_outside_probability(self):
        logits, labels, strong = self.fixture()
        loss, binary, weak = ReviewedFocalLoss()(logits, labels, strong)
        expected = (2 * .8**1.5 * -math.log(.2) + .2**1.5 * -math.log(.8)) / 3
        self.assertAlmostEqual(loss.item(), expected, places=6)
        torch.testing.assert_close(loss, binary)
        self.assertEqual(weak.item(), 0)

    def test_gamma_zero_reproduces_5b_ce_values_and_gradients(self):
        logits, labels, strong = self.fixture()
        other = logits.detach().clone().requires_grad_()
        focal = ReviewedFocalLoss(gamma=0)(logits, labels, strong)[0]
        ce = conservative_loss(other, labels, strong)[0]
        focal.backward()
        ce.backward()
        torch.testing.assert_close(focal, ce)
        torch.testing.assert_close(logits.grad, other.grad)

    def test_focal_gradient_matches_finite_difference(self):
        logits, labels, strong = self.fixture()
        objective = ReviewedFocalLoss(dice_weight=.5)
        objective(logits, labels, strong)[0].backward()
        for column in (0, 1):
            plus, minus = logits.detach().clone(), logits.detach().clone()
            plus[0, 1, 0, column] += .01
            minus[0, 1, 0, column] -= .01
            numerical = (objective(plus, labels, strong)[0] - objective(minus, labels, strong)[0]) / .02
            self.assertAlmostEqual(numerical.item(), logits.grad[0, 1, 0, column].item(), delta=2e-5)

    def test_ignore_has_zero_gradient_even_with_dice(self):
        logits, labels, strong = self.fixture()
        objective = ReviewedFocalLoss(dice_weight=.5)
        loss = objective(logits, labels, strong)[0]
        changed = logits.detach().clone()
        changed[:, :, :, 2] = torch.tensor([1000., -1000.]).reshape(1, 2, 1)
        torch.testing.assert_close(loss, objective(changed, labels, strong)[0])
        loss.backward()
        self.assertEqual(logits.grad[:, :, :, 2].abs().sum().item(), 0)

    def test_all_unknown_gives_differentiable_zero(self):
        logits = torch.randn(2, 2, 3, 4, requires_grad=True)
        loss = ReviewedFocalLoss(dice_weight=.5)(logits, torch.full((2, 3, 4), 255), torch.tensor([True, False]))[0]
        loss.backward()
        self.assertEqual(loss.item(), 0)
        self.assertEqual(logits.grad.abs().sum().item(), 0)

    def test_dice_averages_both_classes_and_only_reviewed_images(self):
        logits = torch.zeros(2, 2, 1, 2, requires_grad=True)
        labels = torch.tensor([[[0, 1]], [[1, 255]]])
        objective = ReviewedFocalLoss(dice_weight=.5)
        loss, binary, weak = objective(logits, labels, torch.tensor([True, False]))
        expected_dice = 1 - (1 + 1e-6) / (2 + 1e-6)
        self.assertAlmostEqual(objective.last_metrics["strong_soft_dice"].item(), expected_dice, places=6)
        torch.testing.assert_close(loss, binary + .5 * weak)
        self.assertTrue(all(not value.requires_grad for value in objective.last_metrics.values()))
        weak_only = objective(logits[1:], labels[1:], torch.tensor([False]))
        torch.testing.assert_close(weak_only[0], .5 * weak_only[2])
        self.assertEqual(weak_only[1].item(), 0)
        self.assertEqual(objective.last_metrics["strong_soft_dice"].item(), 0)

    def test_repeating_weak_images_does_not_amplify_their_group(self):
        logits = torch.randn(2, 2, 2, 2)
        labels = torch.tensor([[[0, 1], [0, 255]], [[1, 255], [1, 255]]])
        objective = ReviewedFocalLoss(dice_weight=.5)
        loss = objective(logits, labels, torch.tensor([True, False]))[0]
        repeated = objective(torch.cat((logits[:1], logits[1:].repeat(7, 1, 1, 1))),
                             torch.cat((labels[:1], labels[1:].repeat(7, 1, 1))),
                             torch.tensor([True] + [False] * 7))[0]
        torch.testing.assert_close(loss, repeated)

    def test_extreme_logits_and_empty_foreground_have_finite_gradients(self):
        for gamma in (0., .1, 1.5, 2.):
            logits = torch.tensor([[[[1000., -1000.]], [[-1000., 1000.]]]], requires_grad=True)
            loss = ReviewedFocalLoss(gamma=gamma, dice_weight=.5)(logits, torch.zeros(1, 1, 2, dtype=torch.long), torch.tensor([True]))[0]
            loss.backward()
            self.assertTrue(torch.isfinite(loss))
            self.assertTrue(torch.isfinite(logits.grad).all())

    def test_class_weight_cap(self):
        logits, labels, strong = self.fixture()
        capped = ReviewedFocalLoss(background_weight=100, class_weight_cap=4)
        self.assertEqual(capped.class_weights, (4, 1))
        torch.testing.assert_close(capped(logits, labels, strong)[0],
                                   ReviewedFocalLoss(background_weight=4)(logits, labels, strong)[0])

    def test_fractional_weights_normalize_sparse_masks_without_underweighting(self):
        logits, labels, strong = self.fixture()
        labels[0, 0, 1] = 255
        normal = ReviewedFocalLoss()(logits, labels, strong)[0]
        small = ReviewedFocalLoss(background_weight=.2, sidewalk_weight=.1)(logits, labels, strong)[0]
        torch.testing.assert_close(normal, small)

    def test_effective_weights_cannot_underflow_fp32(self):
        with self.assertRaisesRegex(ValueError, "FP32"):
            ReviewedFocalLoss(background_weight=1e-100)

    def test_invalid_coefficients_and_shapes_fail(self):
        for keyword in ("gamma", "background_weight", "sidewalk_weight", "class_weight_cap", "dice_weight", "dice_smooth"):
            for value in (-1., math.nan, math.inf):
                with self.subTest(keyword=keyword, value=value), self.assertRaises(ValueError):
                    ReviewedFocalLoss(**{keyword: value})
        for keyword in ("background_weight", "sidewalk_weight", "class_weight_cap", "dice_smooth"):
            with self.assertRaises(ValueError):
                ReviewedFocalLoss(**{keyword: 0.})
        logits, labels, strong = self.fixture()
        for weight in (-1., math.nan, math.inf):
            with self.assertRaises(ValueError):
                ReviewedFocalLoss()(logits, labels, strong, weight)
        with self.assertRaisesRegex(ValueError, "FP32"):
            ReviewedFocalLoss()(logits.half(), labels, strong)
        with self.assertRaisesRegex(ValueError, "Expected logits"):
            ReviewedFocalLoss()(logits, labels, strong.long())


if __name__ == "__main__":
    unittest.main()
