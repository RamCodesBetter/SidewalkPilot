# Train/Validation Leakage

Consecutive driving frames are often near-duplicates. If neighboring frames land
on opposite sides of a split, validation can overstate generalization.

## Current Series 3/4 Split

`series_3_sidewalkpilot_trainer.py` sorts samples by path, cuts the ordered list
into contiguous windows of 100 samples, and assigns approximately every Nth
window to validation. With the default `--val-split 0.10`, approximately 10% of
the windows are held out.

This is materially better than a frame-level random split for dense captures:
most immediate neighbors stay together. It is still not a complete run-group
split. Windows from one capture run can appear in both sets, and the frames near
a window boundary can remain visually similar.

Series 1/2 retains its older seeded frame-level `random_split`, so historical
validation values from that trainer carry a higher near-duplicate leakage risk.

## Augmentation Boundary

Both trainer families build clean and augmented dataset views. Only training
indices use the augmented view; validation reads clean images. This prevents a
synthetic augmentation from becoming validation input, but it does not by itself
solve scene similarity across the split.

## Audit Evidence

The tracked `code/test_files/data/dataset_cosine_similarity.py`,
`code/test_files/data/dataset_clusters.py`, and related
analysis scripts can support a nearest-neighbor audit. Generated embedding and
HTML outputs under a local `code/test_files/data/` directory are working files,
not published artifacts in this branch. There is no checked-in command that
currently turns them into a complete cross-split leakage report. Therefore the
docs claim only the implemented window split, not measured zero leakage.

A stronger future audit would:

1. Reconstruct the exact train/validation indices for the saved dataset revision;
2. Group by capture run and timestamp;
3. Measure each validation frame's nearest training-frame similarity;
4. Report high-similarity cross-split pairs for review.

## Interpretation

Validation metrics are useful for checkpoint screening, not proof of field
performance. The common 6,952-frame evaluation and supervised physical testing
remain separate gates.

## Related Pages

- [Validation Split](../../research-and-math/machine-learning/validation-split.md)
- [Dataset Overview](../../data/dataset-overview.md)
- [Offline Evaluation](../../model-evaluation/offline-evaluation/overview.md)
