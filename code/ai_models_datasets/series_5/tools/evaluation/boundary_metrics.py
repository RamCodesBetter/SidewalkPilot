"""Micro-averaged sidewalk boundary F1 at original reference resolution."""
import numpy as np
from scipy.ndimage import binary_dilation, generate_binary_structure


RADIUS = 2
_axis = np.arange(-RADIUS, RADIUS + 1)
_disk = _axis[:, None]**2 + _axis**2 <= RADIUS**2
_cross = generate_binary_structure(2, 1)


def boundary_counts(prediction, target):
    pred, ref = np.asarray(prediction), np.asarray(target)
    known = ref != 255

    def edge(labels):
        # Inner sidewalk edge only across an observed sidewalk/background pair.
        # Neither the image frame nor unknown pixels constitute background.
        return (labels == 1) & known & binary_dilation((labels == 0) & known, structure=_cross)

    p, r = edge(pred), edge(ref)
    return np.array([np.count_nonzero(p & binary_dilation(r, structure=_disk)), p.sum(),
                     np.count_nonzero(r & binary_dilation(p, structure=_disk)), r.sum()], dtype=np.int64)


def boundary_f1(counts):
    pm, pn, rm, rn = map(int, counts)
    if pn + rn == 0:
        return None
    return (2 * pm * rm / (pm * rn + rm * pn)) if pm and rm else 0.0
