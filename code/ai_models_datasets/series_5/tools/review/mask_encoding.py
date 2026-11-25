"""Encode class-ID masks in the offline viewers' row-major [value, count] format."""
import numpy as np


def encode_labels(mask):
    flat = np.asarray(mask).ravel()
    if not len(flat) or not np.isin(flat, (0, 1, 255)).all():
        raise ValueError("Expected binary labels and optional uncertainty")
    starts = np.r_[0, np.flatnonzero(flat[1:] != flat[:-1]) + 1]
    lengths = np.diff(np.r_[starts, len(flat)])
    return np.column_stack((flat[starts], lengths)).ravel().tolist()
