# Validation Split

Every SidewalkPilot training run holds out a fraction of the labeled frames as a validation set. Series 1/2 and Series 3/4 do not currently use the same split algorithm, so their validation numbers must retain trainer and dataset context.

## How the split is made

Series 3/4 sorts samples by path, divides them into contiguous 100-sample windows, and assigns every Nth complete window to validation:

```python
order = sorted(range(n), key=lambda i: str(base_dataset.samples[i][0]))
window = 100
num_windows = max(1, (n + window - 1) // window)
val_windows = max(1, round(num_windows * args.val_split))
stride = max(1, num_windows // val_windows)
# Whole blocks where w % stride == 0 become validation.
```

Key properties:

- `--val-split 0.10` determines the approximate number of held-out windows.
- Sorting by the timestamp-bearing path makes the split deterministic for an unchanged dataset.
- Keeping adjacent samples together reduces train/validation leakage from near-consecutive captures. It does not prove independence at the two edges of each window.
- Series 1/2 still uses a seeded 90/10 `random_split` with seed 42.

| Field | Value |
|---|---|
| Series 3/4 mechanism | path-sorted 100-sample windows, approximately 10% held out |
| Series 1/2 mechanism | seeded 90/10 `torch.utils.data.random_split` |
| Trainers | `series_3_and_4/series_3_sidewalkpilot_trainer.py`; `series_1_and_2/sidewalkpilot_trainer.py` |

## Augmentation only touches training

A subtle but important detail: the trainer builds the dataset **twice**. `base_dataset` is scanned with `augment=False`; a second `augmented_dataset` is scanned with `augment=True`. The training subset wraps the augmented copy, while the validation subset comes from the clean base copy:

```python
train_subset = Subset(augmented_dataset, train_base_subset.indices)
val_loader   = build_loader(val_subset, ...)   # from base_dataset, no augmentation
```

So the model trains on jittered/shadowed frames but is **validated on clean, un-augmented images**. This makes `steering_mae` a held-out clean-frame metric under the stated split. It does not remove the window-boundary, route-overlap, label-quality, or field-generalization limits below.

## Weighted sampling is training-only too

The training loader uses a `WeightedRandomSampler` (`make_weighted_sampler`) that oversamples rare turn buckets and correction frames up to `--samples-per-epoch` (default `50000`) draws with replacement. Validation uses a plain, unshuffled loader over the held-out indices — no re-weighting — so the reported metrics reflect the true label distribution, not the balanced training distribution.

## What the split reports

At each epoch end, `evaluate()` runs the model over `val_loader`. Series 3 reports validation loss, steering MAE, throttle MAE, ranges, and bucket counts. Series 4 reports its steering-focused losses and current-target MAE. The checked-in Series 3 and Series 4 trainers save the paired `b`/best artifact when **steering MAE** improves; Series 1/2 use validation loss. Final-epoch weights are saved separately.

## Worked example

For 81,237 frames, the Series 3/4 code creates 813 windows of at most 100
samples. Approximately 10% of those windows are selected for validation:

```
num_windows = ceil(81237 / 100) = 813
val_windows = round(813 * 0.10) = 81
stride      = 813 // 81 = 10
```

Every 10th window is held out. In this example the final 37-frame window is also selected
because its zero-based index is 812, not a multiple of 10; therefore it is not held out. The
exact frame count therefore follows the code's window/stride arithmetic rather
than a direct 90/10 frame count.

## What can go wrong

- **Series 1/2 random splitting can leak near-duplicates.** Its historical validation metrics should be read with that limitation.
- **Series 3/4 windows are not run-group splits.** They reduce adjacent-frame leakage but do not guarantee that all frames from one capture run stay on one side. A run-group split remains a possible stronger design.
- **Small `val_split` on a small dataset** gives a noisy MAE. The `max(1, ...)` guard prevents an empty val set but does not make a tiny val set reliable.
- **Do not trust validation MAE alone.** On a straight-heavy set it can reward center bias; read the class and turn metrics too (see `overfitting-risk.md`).

## Related pages

- `research-and-math/machine-learning/regression-framing.md`
- `ai-and-models/training-pipeline/overview.md`
- `autonomy-stack/navigation/overview.md`
