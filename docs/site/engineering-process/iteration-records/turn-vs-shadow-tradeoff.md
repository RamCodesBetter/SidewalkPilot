# Turn vs Shadow Tradeoff

Field tests exposed two different steering failures: missing a real turn and
following a strong shadow edge as though it were the sidewalk boundary. Both are
important, but the project has not proved that they are controlled by one scalar
"turn eagerness" setting.

## What was observed

- Some earlier checkpoints resisted shadows but failed to commit strongly enough
  to real turns.
- Other checkpoints followed diagonal shadow boundaries.
- v3.3 and v3.3b regressed in field testing relative to their Series 2/3
  comparison baselines.
- v3.4 handled every shadow case presented in the July 2026 field test and also
  completed the tested left and right turns. That is a field result, not proof of
  robustness to every lighting condition.

## Plausible explanation

A dark diagonal region can resemble a geometric path edge. Dataset balance,
augmentation, model capacity, and labels may all affect how the model resolves
that ambiguity. Synthetic shadow bands can increase exposure to lighting
variation, while real turn-in-shadow captures preserve the actual camera,
surface, route, and steering target together.

Those mechanisms are plausible engineering explanations. No controlled ablation
has isolated one as the cause of a specific checkpoint's field behavior.

## Current training behavior

The Series 3 trainer balances its seven sampling bands with inverse-frequency
weights raised to `sampler_balance_power` (default `0.3`) and optional source
weights, while the loss applies weights to the nine output classes. The current sampler does not use the legacy
`steering_magnitude_weight()` helper. Training also includes configurable color,
lighting, flip, and synthetic-shadow augmentation.

The 81,237-frame Series 3/4 dataset and the v3.4 training configuration produced
the current field-selected result. Future collection should remain
failure-driven, especially for weak turn classes under difficult lighting.

## How to test the hypothesis

1. Keep the dataset membership, split, seed, and evaluation subset fixed.
2. Change one sampling or augmentation setting at a time.
3. Compare Bal9, turn recall, straight recall, and confusion matrices.
4. Repeat the same left-turn, right-turn, and shadow field route.
5. Promote only when both offline and repeated field evidence improve.

## Related pages

- [Turn Coverage](../../data-governance/data-quality/turn-coverage.md)
- [Shadow Augmentation and Flip](shadow-aug-and-flip.md)
- [Model Retest Plan](../../testing/field-testing/model-retest-plan.md)
