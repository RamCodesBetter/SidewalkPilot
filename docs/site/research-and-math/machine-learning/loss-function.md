# Model Framing and Loss

All model families use the same logical steering convention: `0` degrees is left, `90` is center, and `180` is right. Their output heads and losses differ.

## Direct Regression

Series 1/2 and v3.0 predict continuous controls directly and use Smooth L1-based regression. Direct regression is compact, but common near-straight labels can dominate its aggregate objective.

## Class Plus Local Regression

Most Series 3 models predict 19 values: nine steering-class logits, nine local offsets, and throttle. The decoded result remains a continuous steering angle. Its training objective combines focal-weighted class loss, Smooth L1 loss for the true class's offset, and an optional throttle loss:

```text
total = focal_cross_entropy(class)
      + offset_weight * smooth_l1(selected_offset)
      + throttle_weight * smooth_l1(throttle, target_throttle)
```

Series 3 defaults include class-weight power `0.3`, focal gamma `1.5`, and offset weight `1.0`. Steering-focused runs explicitly set throttle weight to zero; current defaults are not evidence of an older checkpoint's command.

## Series 4 Temporal Framing

Series 4 removes throttle and uses an 18-value class-plus-offset steering head per horizon:

- PC (`4.0p/r`) supplies the image plus causal previous steering targets and predicts the current target;
- CF (`4.0f/g`) supplies the image and predicts current plus future targets;
- PCF (`4.0a/c`) combines causal previous-target inputs with current and future supervision.

Future steering values are labels during training. They are never future inputs at deployment. Fixed Series 4 runs use class-weight power `0.5`, focal gamma `1.5`, no sampler balancing, and future-horizon decay `0.70` where applicable.

## Gradient Norm and Limits

The trainers log gradient norm before clipping and clip to a maximum norm of `1.0`. Gradient norm diagnoses update stability; it is not a quality score. The losses also do not encode stopping distance, sidewalk boundaries, or physical smoothness. Offline class-balanced evaluation and supervised driving remain required.

See [CNN Architecture](../../ai-and-models/architecture/cnn.md), [Series 3 Hybrid Head](../../ai-and-models/architecture/series-3-hybrid-head.md), and [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md).
