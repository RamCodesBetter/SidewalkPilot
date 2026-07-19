# Turn Versus Shadow Tradeoff

Field tests exposed two different steering failures: missing a real turn and
following a strong shadow edge as though it were the sidewalk boundary. Both are
important, but the project has not proved that they are controlled by one scalar
"turn eagerness" setting.

## What Was Observed

- Some earlier checkpoints resisted shadows but failed to commit strongly enough
  to real turns.
- Other checkpoints followed diagonal shadow boundaries.
- v3.3 and v3.3b regressed in field testing relative to their Series 2/3
  comparison baselines.
- v3.4 handled every shadow case presented in the July 2026 field test and also
  completed the tested left and right turns. That is a field result, not proof of
  robustness to every lighting condition.
- Some weak checkpoints also produced endpoint-heavy or visibly stepped steering. This
  "bang-bang" symptom can be measured through predicted-class distributions, confusion
  matrices, command telemetry, and synchronized video, but those observations do not
  identify one root cause by themselves.

## Plausible Explanation

A dark diagonal region can resemble a geometric path edge. Dataset balance,
augmentation, model capacity, and labels may all affect how the model resolves
that ambiguity. Synthetic shadow bands can increase exposure to lighting
variation, while real turn-in-shadow captures preserve the actual camera,
surface, route, and steering target together.

Those mechanisms are plausible engineering explanations. No controlled ablation
has isolated one as the cause of a specific checkpoint's field behavior.

## Current Training Behavior

The Series 3 trainer can rebalance seven sampling bands with inverse-frequency
weights raised to `sampler_balance_power`; its parser default is `0.3`. It also
supports source weights, while the loss applies weights to the nine output
classes. The sampler does not use the legacy `steering_magnitude_weight()`
helper. Training also includes configurable color, lighting, flip, and
synthetic-shadow augmentation.

The v3.4 and Series 4 runs set `sampler_balance_power=0.0`, used deterministic
left and right balance flipping, and applied class weighting in the loss. Their
81,237-image root contained only real images, so CARLA and correction-source
weights did not affect those runs.

The 81,237-image Series 3/4 dataset and the v3.4 training configuration produced
the current field-selected result. Future collection should remain
failure-driven, especially for weak turn classes under difficult lighting.

Implemented augmentation includes synthetic diagonal, tree, edge, mixed-lighting, glare,
color, texture, and label-aware horizontal-flip paths. A flip mirrors the image and maps
steering to `180 - steering`. The exact v3.3 command and resolved probabilities were not
preserved, so current trainer defaults cannot be presented as the historical v3.3 setup.
No controlled ablation proved that one augmentation or sampler parameter caused its field
regression.

## How to Test the Hypothesis

1. Keep the dataset membership, split, seed, and evaluation subset fixed.
2. Change one sampling or augmentation setting at a time.
3. Compare Bal9, turn recall, straight recall, and confusion matrices.
4. Repeat the same left-turn, right-turn, and shadow field route.
5. Promote only when both offline and repeated field evidence improve.

## Related Pages

- [Data Quality](../../data-governance/data-quality/image-quality-checks.md)
- [Training Pipeline](../../ai-and-models/training-pipeline/overview.md)
- [Field Testing](../../testing/field-testing/overview.md)
