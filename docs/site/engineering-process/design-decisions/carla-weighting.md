# CARLA Weighting

This decision controls what happens **when** pre-generated CARLA samples are included in a
training run. It does not assert that every historical model used CARLA.

## Decision

Both trainer generations use the same default source factors:

```python
def source_weight(source, real_weight=2.0, carla_weight=0.6, correction_weight=3.0):
    if source == "carla":
        return carla_weight
    if source == "correction":
        return correction_weight
    return real_weight
```

The source factor is multiplied by the trainer's class/bucket balancing factor. The
Series 1/2 sampler additionally multiplies by steering-magnitude weight. Therefore `0.6`
is not a percentage and does not describe the final fraction of synthetic samples drawn.
It only makes a CARLA sample less likely than an otherwise comparable real or corrected
sample.

## Why Down-Weight Synthetic Data

CARLA can add inexpensive pose, route, and weather variety, but simulator textures,
lighting, camera geometry, and object appearance do not exactly match the physical car.
The chosen ordering is therefore:

```text
correction 3.0 > real 2.0 > CARLA 0.6
```

Human corrections receive the highest factor because they target known label failures.
Real camera data remains the main reference distribution. Synthetic data can supplement
coverage without dominating it.

## Current Use

The current Series 3/4 dataset contains 81,237 real captures. The Series 4 PC, CF,
and PCF runs used those same images. CARLA dataset repositories remain available as
separate artifacts, and the trainer still supports them as explicit roots.

Do not infer the source mix of an older Series 1/2 or Series 3 checkpoint from trainer
defaults. Confirm it from that run's command, W&B configuration, or printed source counts.
If those records are unavailable, document the source mix as unknown.

## Verification Gate

At the start of a run, save the trainer's source-count and sampler-weight output. A run
described as real-only must list no `carla` source. A CARLA-assisted run must name the
CARLA root and show its source count.

## Related Pages

- `research-and-math/machine-learning/sim-to-real-gap.md`
- `ai-and-models/training-pipeline/source-weights.md`
- `engineering-process/design-decisions/correction-json-as-label-source.md`
