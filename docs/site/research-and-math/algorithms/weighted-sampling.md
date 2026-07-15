# Weighted Sampling

The trainers use `torch.utils.data.WeightedRandomSampler` to control how often
each training sample appears in an epoch. Validation is never weighted.

## Current Series 3 Formula

The sampler first counts the seven coarse steering buckets and takes the median
non-empty count as `target_count`. For a sample in bucket `b`:

```text
bucket_weight = (target_count / count[b]) ** sampler_balance_power
sample_weight = bucket_weight * source_weight
```

The Series 3 default `sampler_balance_power` is `0.3`, so rebalancing is gentle.
`0.0` preserves the natural bucket distribution; `1.0` applies full inverse
frequency. Source defaults are real `2.0`, CARLA-tagged `0.6`, and correction
`3.0`. The sampler draws 50,000 examples per epoch by default, with replacement.

The fixed Series 4 experiments used `sampler_balance_power=0.0`, after
deterministic left/right balance flipping, and moved more class-balancing
pressure into the loss with `class_weight_power=0.5`. That is an experiment
configuration difference, not a change to the Series 3 trainer's defaults.

The function `steering_magnitude_weight()` still exists in the trainer, and a
legacy CLI value is logged for compatibility, but the current Series 3 sampler
does **not** multiply by it. The source code comment explicitly leaves magnitude
weighting out because the hybrid focal/class loss already addresses steering
imbalance.

## Worked Example

If the median non-empty count is 800, one bucket contains 400 samples, and another
contains 20,000:

```text
rare bucket:     (800 / 400) ** 0.3   = 1.231
straight bucket: (800 / 20000) ** 0.3 = 0.381
```

For two real samples, the shared `2.0` source multiplier cancels in their relative
probability, so the rare-bucket sample is about `1.231 / 0.381 = 3.23` times as
likely to be drawn. This is much gentler than full inverse-frequency balancing.

## Why It Is Not a Quality Metric

Sampling pressure can expose the model to rare turns more often, but it cannot
create missing scene diversity. Excessive rebalancing can also over-repeat a
small set of frames and distort the natural straight prior. Preserve the exact
command and W&B configuration for each run instead of assuming current defaults
describe historical checkpoints.

## Related Pages

- [Sampler](../../ai-and-models/training-pipeline/sampler.md)
- [Source Weights](../../ai-and-models/training-pipeline/source-weights.md)
- [Turn Coverage](../../data-governance/data-quality/turn-coverage.md)
