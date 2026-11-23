"""Avoid learning questionable tiny negative regions from SAM pseudo-labels."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import numpy as np
from scipy import ndimage


POLICY = {
    "version": "pseudo-negative-islands-ignore-v1",
    "maximum_negative_component_pixels_at_720p": 4096,
    "action": "Convert small negative components to 255, never to sidewalk",
    "scope": "Pseudo-labels only; reviewed targets remain unchanged",
    "limitation": "May also ignore small genuine foreground objects; does not certify the remaining labels",
}


def prepare_target(labels):
    labels = np.asarray(labels)
    if labels.ndim != 2 or not labels.size or not np.isin(labels, (0, 1, 255)).all():
        raise ValueError("Expected a nonempty 0/1/255 pseudo-label")
    components, _ = ndimage.label(labels == 0, structure=np.ones((3, 3), dtype=np.uint8))
    sizes = np.bincount(components.ravel())
    maximum = max(1, round(POLICY['maximum_negative_component_pixels_at_720p'] * labels.size / (1280 * 720)))
    uncertain = sizes <= maximum
    uncertain[0] = False
    changed = uncertain[components]
    result = labels.astype(np.uint8, copy=True)
    result[changed] = 255
    return result, {"additional_ignored_negative_pixels": int(changed.sum()),
                    "negative_component_threshold_pixels": maximum}
