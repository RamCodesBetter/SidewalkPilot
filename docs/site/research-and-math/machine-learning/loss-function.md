# Model Framing and Loss

All model families use the same logical steering convention: `0` degrees is left, `90` is center, and `180` is right. Their output heads and losses differ.

## Direct Regression

Series 1/2 and v3.0 predict continuous controls directly and use Smooth L1-based regression. Direct regression is compact, but common near-straight labels can dominate its aggregate objective.

## Class Plus Local Regression

Most Series 3 models predict 19 values: nine steering-class logits `z`, nine raw local offsets `o`, and one raw throttle value `t`. A target steering angle is converted into a class index `y` and a fractional position `u` from 0 to 1 inside that class. For each sample, the active code computes:

```text
ce = cross_entropy(z, y, class_weights)
class_loss = mean((1 - exp(-ce))^focal_gamma * ce)

predicted_offset = sigmoid(o[y])
offset_loss = smooth_l1(predicted_offset, u)

predicted_throttle = sigmoid(t)
throttle_loss = smooth_l1(predicted_throttle, target_throttle)

total_loss = class_loss
           + offset_weight * offset_loss
           + throttle_weight * throttle_loss
```

The offset loss does **not** compare all nine offsets with the steering angle. Only the offset belonging to the target class is supervised, and it is compared with the target's normalized within-class fraction. Cross-entropy already uses all nine logits.

Backpropagation starts from the one scalar `total_loss`. Its gradient still flows through every output that contributed to that scalar: all nine class logits, the target class's offset, and throttle when its weight is nonzero. Series 3 defaults include class-weight power `0.3`, focal gamma `1.5`, and offset weight `1.0`. Steering-focused runs explicitly set throttle weight to zero; current defaults are not evidence of an older checkpoint's command.

## Series 4 Temporal Framing

Series 4 removes throttle and uses an 18-value class-plus-offset steering head per horizon:

- PC (`4.0p/r`) supplies the image plus causal previous steering targets and predicts the current target;
- CF (`4.0f/g`) supplies the image and predicts current plus future targets;
- PCF (`4.0a/c`) combines causal previous-target inputs with current and future supervision.

Future steering values are labels during training. They are never future inputs at deployment. For `H` predicted horizons, the common base loss is:

```text
horizon_weight[h] = horizon_decay^h

series4_loss =
    sum(horizon_weight[h] * (class_loss[h] + offset_weight * offset_loss[h]))
    / sum(horizon_weight[h])
```

PC has one horizon, so the normalized weight is 1. CF and PCF have four horizons. Fixed Series 4 runs use class-weight power `0.5`, focal gamma `1.5`, no sampler balancing, and future-horizon decay `0.70` where applicable. Series 4.1 can add separately weighted trajectory, history-consistency, counterfactual-history, or closed-loop terms according to the selected training profile.

## Gradient Norm and Limits

The trainers log gradient norm before clipping and clip to a maximum norm of `1.0`. Gradient norm diagnoses update stability; it is not a quality score. The losses also do not encode stopping distance, sidewalk boundaries, or physical smoothness. Offline class-balanced evaluation and supervised driving remain required.

See [CNN Architecture](../../ai-and-models/architecture/cnn.md), [Series 3 Hybrid Head](../../ai-and-models/architecture/series-3-hybrid-head.md), and [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md).
