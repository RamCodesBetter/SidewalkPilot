# Sim-To-Real Gap

The sim-to-real gap is the performance loss that can appear when synthetic images differ
from the real camera, chassis, lighting, and sidewalk. SidewalkPilot's trainers can consume
pre-generated CARLA datasets, but they do not start CARLA, connect to a simulator, or render
frames. Every input is an image and label already stored on disk.

## Verified Data Paths

Both trainer generations infer a sample source from its dataset-root name:

- Names containing `carla`, `synthetic`, `sim`, or `dataset_l2` become `carla`;
- Ordinary capture roots become `real`;
- Hand-corrected samples are tagged `correction`.

When those sources are present, the weighted sampler defaults to:

```text
real       2.0
carla      0.6
correction 3.0
```

These are relative factors inside a sampler that also balances steering classes. They do
not mean that every training run contained all three sources. If a run has no CARLA root,
the `0.6` path is unused.

The current shared Series 3/4 dataset contains **81,237 labeled real images**. The six
v4.0/v4.1 Series 4 experiments were run against that same dataset. Historical CARLA datasets are
published separately, but a checkpoint should be described as CARLA-assisted only when its
saved training command, run configuration, or source-count log proves that a CARLA root was
included. Folder defaults in trainer code are not enough to prove historical usage.

## Domain-Shift Defenses

The Series 3/4 augmentation stack changes geometry and appearance while preserving label
meaning:

- Camera translation, rotation, and scale, with steering adjusted for horizontal shift;
- Contrast, brightness, channel gain/bias, optional HSV jitter, and optional CLAHE;
- Diagonal, mixed-light, tree-shadow, edge-shadow, and patchy-concrete effects;
- Glare, haze, rain, lens droplets, and wet-reflection effects;
- Additional CARLA-only randomization when a sample is actually tagged `carla`.

Augmentation broadens the training distribution, but it is not evidence that a model will
handle a specific real condition. That requires a frozen offline comparison and a field
test of the condition itself.

## Current Evidence

The July 13 field comparison selected v3.4 over v3.3, v3.3b, and v3.4b after the presented
normal-turn and harsh-shadow cases. This supports v3.4 as the current field baseline; it
does not prove complete shadow robustness across routes, seasons, or camera conditions.
v4.0 also has a bounded field comparison: image-only v4.0f remained viable, while the
history-input models exposed a closed-loop steering-echo failure that open-loop metrics did
not predict. v4.1 correction models have common-set offline results but still need live
integration and physical comparison.

## Reporting Rule

For every future checkpoint, preserve:

1. The exact `--roots` argument;
2. Trainer source counts;
3. The frozen split identity;
4. Augmentation arguments;
5. Checkpoint and ONNX hashes;
6. The field-test route and conditions.

That record turns “CARLA-assisted,” “real-only,” and “shadow-hardened” from assumptions into
auditable facts.

## Related Pages

- `engineering-process/design-decisions/carla-weighting.md`
- `ai-and-models/training-pipeline/source-weights.md`
- `model-evaluation/field-evaluation/shadow-robustness.md`
