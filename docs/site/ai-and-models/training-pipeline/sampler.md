# Sampler

The sampler documents how the trainer chooses which examples to show the model each epoch. It should not see the dataset in raw order, because a manual-driving dataset is dominated by straight-ahead frames. Without rebalancing, a model can post a great validation loss while quietly predicting "straight" almost everywhere — the exact failure this sampler exists to prevent.

## How it works

- Series 3/4 use path-sorted 100-sample split windows to reduce adjacent-frame leakage; this is not a complete run-group split.
- The training split uses a `WeightedRandomSampler` built by `make_weighted_sampler`. Each training index gets a weight that is the product of two factors:
  - **Steering-bucket weight** — `(median(nonzero bucket counts) / this bucket's count) ** sampler_balance_power`. The Series 3 default is `0.3`, which softens inverse-frequency balancing. The fixed Series 4 experiments used `0.0`, preserving the post-flip natural distribution while applying stronger class weights in the loss.
  - **Source weight** (`source_weight`) — real `2.0`, CARLA `0.6`, correction `3.0` by default.
- `--samples-per-epoch` (default `50000`) sets how many draws happen per epoch with replacement, decoupling epoch length from raw dataset size.
- The seven steering buckets used for balancing are: hard-left `0..45`, left `45..75`, soft-left `75..85`, straight `85..95`, soft-right `95..105`, right `105..135`, hard-right `135..180`.

## Why this choice

- Manual driving is mostly straight, so raw-order or uniform sampling makes "predict straight" a low-loss local optimum.
- Corrections and field-failure cases need extra sampling pressure (higher source weight plus `repeat` duplication) so the model genuinely learns them instead of averaging them away.
- `steering_magnitude_weight()` remains in the Series 3 trainer, but its current sampler intentionally does not use it; class-weighted focal loss provides the additional nine-class pressure. Series 4 does not use that legacy helper.

## Sampler inputs

| Input | Purpose |
|---|---|
| Steering bucket | Rebalance rare turns against dominant straight frames |
| Source type | Balance real, CARLA, and correction samples |
| `samples_per_epoch` | Control training length independent of raw dataset size |
| Balance power | Tune rebalancing from natural (`0.0`) to full inverse frequency (`1.0`) |

## Note on throttle

Series 3 buckets and weights are computed on steering. Steering-focused Series 3 runs use zero throttle-loss weight because the captured throttle distribution does not support the desired learned-throttle claim. Series 4 removes throttle from the model output entirely.

## Status note

Sampler configuration is part of a run's evidence. Preserve bucket counts, source counts, command-line values, and W&B config rather than treating the defaults on this page as proof of what an older checkpoint used.

## Evidence to attach

- `make_weighted_sampler` in the trainer
- Bucket distribution logs (`[sampler] servo bucket counts`)
- Source count logs (`[sampler] source counts and weights`)
- Training command flags

## Related pages

- `ai-and-models/training-pipeline/source-weights.md`
- `data-governance/data-quality/turn-coverage.md`
- `research-and-math/algorithms/weighted-sampling.md`
