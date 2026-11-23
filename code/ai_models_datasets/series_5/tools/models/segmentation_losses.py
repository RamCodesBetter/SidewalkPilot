"""5.C binary focal objectives; keep historical 5.A/5.B losses unchanged."""
import math

import torch
import torch.nn.functional as F


class ReviewedFocalLoss:
    """Separate strong/weak image means, with optional reviewed-only soft Dice.

    Returns (total, strong objective, weak focal), matching the shared trainer.
    last_metrics contains detached scalar components for local/W&B logging.
    """

    def __init__(self, *, gamma=1.5, background_weight=2.0, sidewalk_weight=1.0,
                 class_weight_cap=4.0, dice_weight=0.0, dice_smooth=1e-6):
        values = dict(gamma=gamma, background_weight=background_weight,
                      sidewalk_weight=sidewalk_weight, class_weight_cap=class_weight_cap,
                      dice_weight=dice_weight, dice_smooth=dice_smooth)
        for name, value in values.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if min(background_weight, sidewalk_weight, class_weight_cap, dice_smooth) <= 0:
            raise ValueError("Class weights, cap, and Dice smoothing must be positive")
        self.gamma, self.dice_weight, self.dice_smooth = gamma, dice_weight, dice_smooth
        self.class_weights = (min(background_weight, class_weight_cap), min(sidewalk_weight, class_weight_cap))
        if min(self.class_weights) < torch.finfo(torch.float32).tiny:
            raise ValueError("Effective class weights must be representable as normal FP32 values")
        self.last_metrics = {}

    def __call__(self, logits, targets, strong, partial_weight=0.5):
        if not math.isfinite(partial_weight) or partial_weight < 0:
            raise ValueError("Weak-label weight must be finite and nonnegative")
        if logits.dtype != torch.float32:
            raise ValueError("5.C loss requires FP32 logits")
        if (logits.ndim != 4 or logits.shape[1] != 2
                or targets.shape != (logits.shape[0], *logits.shape[2:])
                or strong.shape != (logits.shape[0],) or strong.dtype != torch.bool):
            raise ValueError("Expected logits [N,2,H,W], targets [N,H,W], boolean strong [N]")
        known = targets != 255
        valid = known.flatten(1).any(1)
        zero = logits.sum() * 0
        weights = torch.where(targets == 0, self.class_weights[0], self.class_weights[1]) * known
        # p_t must come from UNWEIGHTED CE; class weighting is outside the focal factor.
        ce = F.cross_entropy(logits, targets, ignore_index=255, reduction="none")
        modulation = (-torch.expm1(-ce)).clamp_min(torch.finfo(logits.dtype).eps).pow(self.gamma)
        denominator = weights.flatten(1).sum(1).clamp_min(torch.finfo(logits.dtype).tiny)
        per_image = (weights * modulation * ce).flatten(1).sum(1) / denominator
        strong_focal = per_image[strong & valid].mean() if (strong & valid).any() else zero
        weak_focal = per_image[~strong & valid].mean() if (~strong & valid).any() else zero
        dice = zero
        if self.dice_weight and (strong & valid).any():
            selected = strong & valid
            selected_known = known[selected, None]
            probabilities = logits[selected].softmax(1) * selected_known
            labels = targets[selected].masked_fill(~known[selected], 0)
            reference = F.one_hot(labels, num_classes=2).permute(0, 3, 1, 2) * selected_known
            intersection = (probabilities * reference).sum((2, 3))
            denominator = probabilities.sum((2, 3)) + reference.sum((2, 3))
            dice = (1 - (2 * intersection + self.dice_smooth) / (denominator + self.dice_smooth)).mean()
        strong_objective = strong_focal + self.dice_weight * dice
        self.last_metrics = {"strong_focal": strong_focal.detach(), "weak_focal": weak_focal.detach(),
                             "strong_soft_dice": dice.detach(), "weighted_dice": (self.dice_weight * dice).detach()}
        return strong_objective + partial_weight * weak_focal, strong_objective, weak_focal
