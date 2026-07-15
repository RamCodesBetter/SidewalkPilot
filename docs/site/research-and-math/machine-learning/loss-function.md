# Loss Function

The model families do not share one loss. Series 1/2 use direct control
regression; Series 3/4 use the hybrid class-plus-offset steering objective.

## Series 1/2

The early trainer predicts steering directly in normalized control space and uses
Smooth L1 loss with its Series 1/2 weighting logic. Those historical models must
be evaluated with their matching architecture and decoder.

## Series 3 Hybrid Loss

For a target steering angle, the trainer derives:

- One of nine steering classes;
- A `0..1` offset within that class;
- The stored throttle target.

The 19-value head contains nine class logits, nine raw offsets, and one raw
throttle value. The current loss is:

```text
total = focal_weighted_cross_entropy(class)
      + offset_loss_weight * SmoothL1(selected_true_class_offset)
      + throttle_loss_weight * SmoothL1(sigmoid(throttle), target_throttle)
```

Only the offset for the true class receives offset supervision. Class weights
come from the Series 3 training split:

```text
class_weight[c] = (mean_nonempty_count / count[c]) ** class_weight_power
```

Series 3 defaults are `class_weight_power=0.3`, `focal_gamma=1.5`,
`offset_loss_weight=1.0`, and `throttle_loss_weight=0.5`. The steering-focused
v3 training pattern explicitly sets throttle weight to `0.0`; current defaults
must not be presented as proof of flags used by an older checkpoint.

## Series 4

Series 4 removes throttle output. Each steering horizon uses the same 18-value
class-plus-offset contract. PC supervises the current horizon; CF and PCF add
three future supervision horizons. The trainer's aggregate loss combines those
horizon losses according to the fixed experiment contract. The three fixed
Series 4 runs used `class_weight_power=0.5`, `focal_gamma=1.5`,
`offset_loss_weight=1.0`, `sampler_balance_power=0.0`, and a future-horizon
decay of `0.70` where future heads exist.

## Gradient Norm

The trainer logs the gradient norm before clipping and clips updates to a maximum
norm of `1.0`. `grad_norm` is a stability diagnostic, not a model-quality score:
a finite varying value shows updates are flowing, while sustained near-zero or
repeated extreme spikes deserve investigation.

## Limits

The loss optimizes an offline objective. It does not encode physical stopping
distance, sidewalk boundaries, or a guarantee of smooth steering. Promotion still
requires class-balanced evaluation and a supervised field test.

## Related Pages

- [Series 3 Hybrid Head](../../ai-and-models/architecture/series-3-hybrid-head.md)
- [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md)
- [Training Metrics](../../ai-and-models/training-pipeline/metrics.md)
