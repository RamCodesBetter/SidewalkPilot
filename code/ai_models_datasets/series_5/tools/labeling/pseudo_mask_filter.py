"""Conservative SAM prompt-agreement filter for explicitly unverified pseudo-labels."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import numpy as np
from scipy import ndimage

POLICY = {
    "version": "sam3-agreement-pseudo-v1", "prompts": ["concrete sidewalk", "sidewalk"],
    "score_threshold": 0.4, "mask_threshold": 0.5,
    "minimum_top_scores": [0.65, 0.55], "minimum_prompt_iou": 0.90,
    "maximum_speck_pixels_at_720p": 128, "boundary_ignore_pixels_at_720p": 2,
    "minimum_positive_fraction": 0.15, "maximum_positive_fraction": 0.94,
    "minimum_negative_fraction": 0.03,
    "labels": {"0": "pseudo background, NOT human verified", "1": "pseudo sidewalk", "255": "ignore/disagreement"},
    "no_hole_filling": True, "no_blanket_largest_component": True,
    "limitation": "Prompt agreement and confidence are screening signals, not proof of accurate labels.",
}


def remove_specks(mask, maximum):
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=np.uint8))
    sizes = np.bincount(labels.ravel())
    keep = sizes > maximum
    keep[0] = False
    output = keep[labels]
    return output, mask & ~output, int(count), int(np.count_nonzero(sizes[1:] > maximum))


def filter_masks(main, alternative, scores, policy=POLICY):
    main, alternative = np.asarray(main), np.asarray(alternative)
    if main.ndim != 2 or main.shape != alternative.shape or not main.size:
        raise ValueError("Expected matching nonempty 2D masks")
    if not np.isin(main, (0, 1)).all() or not np.isin(alternative, (0, 1)).all():
        raise ValueError("Expected binary proposals")
    if len(scores) != 2 or any(not np.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise ValueError("Expected two finite top scores")
    area_scale = main.size / (1280 * 720)
    maximum = max(1, round(policy["maximum_speck_pixels_at_720p"] * area_scale))
    radius = max(1, round(policy["boundary_ignore_pixels_at_720p"] * np.sqrt(area_scale)))
    a, removed_a, components_a, large_a = remove_specks(main.astype(bool), maximum)
    b, removed_b, components_b, large_b = remove_specks(alternative.astype(bool), maximum)
    union, intersection = a | b, a & b
    iou = float(intersection.sum() / union.sum()) if union.any() else 0.0
    # Image borders are not object boundaries: do not erase the bottom sidewalk edge.
    positive = ndimage.binary_erosion(intersection, iterations=radius, border_value=1)
    negative = ndimage.binary_erosion(~union, iterations=radius, border_value=1)
    negative &= ~(removed_a | removed_b)
    result = np.full(main.shape, 255, dtype=np.uint8)
    result[negative], result[positive] = 0, 1
    reasons = []
    if any(s < minimum for s, minimum in zip(scores, policy["minimum_top_scores"])):
        reasons.append("weak_detection")
    if iou < policy["minimum_prompt_iou"]:
        reasons.append("prompt_disagreement")
    fraction = float(positive.mean())
    if not policy["minimum_positive_fraction"] <= fraction <= policy["maximum_positive_fraction"]:
        reasons.append("implausible_coverage")
    if float(negative.mean()) < policy["minimum_negative_fraction"]:
        reasons.append("insufficient_background")
    if large_a > 1 or large_b > 1:
        reasons.append("multiple_substantial_components")
    return result, {"accepted_for_pseudo_training": not reasons, "reasons": reasons,
        "prompt_iou": iou, "positive_fraction": fraction, "negative_fraction": float(negative.mean()),
        "ignored_fraction": float((result == 255).mean()), "top_scores": list(map(float, scores)),
        "removed_speck_pixels": int((removed_a | removed_b).sum()),
        "components_before": [components_a, components_b], "substantial_components": [large_a, large_b],
        "review_status": "unreviewed pseudo-label, not a human reference"}
