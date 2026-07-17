# Training Split and Sampling

SidewalkPilot separates validation from training and adjusts how often training examples are drawn. These are distinct operations: validation remains unweighted and unaugmented.

## Validation Splits

Series 1/2 historically uses a seeded 90/10 random split with seed 42. Because neighboring driving frames are visually similar, this can place near-duplicates on both sides and makes those historical validation numbers optimistic.

Series 3/4 sorts paths, groups adjacent samples into 100-frame windows, and assigns approximately every tenth window to validation. For 81,237 frames this produces 813 windows and approximately 81 validation windows. This reduces adjacent-frame leakage but does not provide full capture-run isolation.

Training uses an augmented dataset copy. Validation uses the clean base copy. Any metric must retain its dataset, trainer, split method, and checkpoint context.

## Weighted Sampling

Series 3 uses `WeightedRandomSampler` with replacement. For steering bucket `b`:

```text
bucket_weight = (median_nonempty_count / count[b]) ^ sampler_balance_power
sample_weight = bucket_weight * source_weight
```

The default Series 3 balance power is `0.3`, with 50,000 draws per epoch. Source weights are correction `3.0`, real `2.0`, and CARLA-tagged `0.6`. These are relative sampling multipliers, not dataset percentages.

The fixed Series 4 experiments use `sampler_balance_power = 0.0`, deterministic left/right balance flipping, and class weighting in the loss. Historical commands and W&B configuration remain the source of truth for a particular run.

## Overfitting and Straight Collapse

Most sidewalk frames are near straight. A model that predicts center for every image can obtain a deceptively low aggregate error while failing turns. The project counters this with augmentation, dropout, weight decay, balanced sampling or class weighting, clean validation, confusion matrices, Bal9, turn recall, and field testing.

Sampling cannot invent missing scene diversity. Excessive rebalancing can repeatedly expose a small set of rare frames, and aggressive augmentation can erase useful turn cues. Promotion therefore never relies on training loss or MAE alone.

See [Training Pipeline](../../ai-and-models/training-pipeline/overview.md), [Offline Evaluation](../../model-evaluation/offline-evaluation/overview.md), and [Data Quality](../../data-governance/data-quality/image-quality-checks.md).
