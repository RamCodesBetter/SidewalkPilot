# Series 3 Hybrid Head

The hybrid head is implemented in Series 3 v3.1 through v3.4b. v3.0 retains the earlier two-output regression contract.

## Output

The v3.1+ head emits 19 values:

```text
0..8   steering-class logits
9..17  one raw local offset per class
18     throttle
```

The nine classes are `HL, L, L+, SL, ST, SR, R, R+, HR` over the absolute 0-to-180 steering range.

## Decode

```text
probabilities = softmax(logits)
class = argmax(probabilities)
fraction = sigmoid(offset_for_selected_class)
steering = class_lower_edge + fraction * class_width
```

Only the selected class's offset affects steering. This provides a coarse turn decision and a continuous position inside that class. The code may take `argmax` directly over the logits because softmax does not change which value is largest.

## Why It Replaced Pure Regression

The dataset contains many more straight frames than sharp turns. Pure average-error training can reduce loss by staying near center. The class term makes turn-category mistakes explicit; the local offset avoids a nine-angle-only controller.

The design still has a discontinuity when the selected class changes. Smoothing, temporal context, and field testing remain necessary because a good validation confusion matrix does not guarantee smooth physical steering.

## Loss

Current Series 3 hybrid training combines focal-weighted class loss, Smooth L1 loss for the true class's local offset, and optional Smooth L1 throttle loss. The v3.4 run used class weighting and deterministic left/right balance flipping. Its sampler drew 50,000 examples per epoch, but did not apply steering-bucket or source reweighting. Steering-focused runs can set throttle loss to zero while preserving the 19-value model output.

## Series 4 Relationship

Series 4 removes throttle and uses 18 values per horizon: the same nine logits plus nine offsets. PC emits one horizon; CF/PCF emit four. This reuses the successful steering representation while testing temporal information separately.

See [CNN Architecture](cnn.md), [Series 4 Temporal Experiments](series-4-plan.md), and [Bal9](../../model-evaluation/offline-evaluation/bal9.md).
