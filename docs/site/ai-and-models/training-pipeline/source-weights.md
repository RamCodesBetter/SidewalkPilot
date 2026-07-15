# Source Weights

Source Weights documents how real driving data, CARLA data, and correction samples are trusted differently during training. Series 3 does not treat every sample type equally by default, because they do not carry equal signal: real frames are what the car actually sees, CARLA frames are cheap coverage with a domain gap, and corrections are surgical fixes for known mistakes.

## How it works

- Every sample is tagged with a source when the dataset is scanned. `source_name_for_root` marks a root as `carla` if its path contains any synthetic marker (`carla`, `dataset_l2`, `synthetic`, `sim`), otherwise `real`; correction entries are tagged `correction`.
- `source_weight` maps that tag to a multiplier, with defaults:

| Source | Default weight | Role |
|---|---:|---|
| Real human driving | `2.0` | Main imitation-learning source |
| CARLA / synthetic | `0.6` | Supplemental controlled coverage, discounted for sim-to-real gap |
| Corrections | `3.0` | High-value targeted fixes for known failures |

- These are set by `--real-sample-weight`, `--carla-sample-weight`, and `--correction-sample-weight`.
- The source weight multiplies the softened steering-bucket weight (see the sampler page). Source weighting changes how often a sample is drawn, not its loss magnitude directly.

## Why this choice

- **Real** data matches the physical RC car and Raspberry Pi Camera Module 3 Wide deployment domain, so its default is `2.0`.
- **CARLA-tagged** roots receive `0.6` by default to account for a sim-to-real gap. The trainer consumes pre-generated files; it does not create simulation coverage on demand.
- **Corrections** target frames the model is already known to get wrong, so they earn the highest weight (`3.0`) — and they can additionally be `repeat`-duplicated. The caution is that this power can overfit a handful of frames if pushed too far, so heavy correction weighting should be a deliberate experiment, not a default reflex.

## Status note

The exact defaults must be read from the trainer version used for a run and preserved in the W&B configuration. The current 81,237-image Series 3/4 dataset is real-world data; the separate CARLA repository is not evidence that a specific release included CARLA unless that run's root list and source counts show it.

## Evidence to attach

- `source_weight` and `source_name_for_root` in the trainer
- Training logs showing source counts
- Evaluation grouped by data source, if added
- Field notes comparing real-heavy vs CARLA-heavy models

## Related pages

- `ai-and-models/training-pipeline/sampler.md`
- `research-and-math/machine-learning/sim-to-real-gap.md`
- `engineering-process/design-decisions/carla-weighting.md`
