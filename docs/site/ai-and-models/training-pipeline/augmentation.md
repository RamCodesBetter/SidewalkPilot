# Augmentation

Augmentation documents the image transformations applied during training to expose the model to more visual variation. Field tests identified shadow and lighting changes as important failure conditions, so Series 3/4 includes strong appearance augmentation and a geometric jitter transform with an approximate label correction. Augmented images are generated during training and are not saved as raw collected data.

## How it works

- Each sample is loaded, resized to the network input size (`320x180`), and then — only for the augmented training dataset — passed through `augment_image` (and an optional flip). Augmenting at input size instead of full JPG resolution keeps oversampled runs cheaper on CPU.
- `augment_image` is a stack of independently-probable transforms. The main ones and their fixed probabilities:

| Transform | Probability | Note |
|---|---:|---|
| Camera jitter (shift/rotate/scale) | 0.75 | Adjusts the steering target from horizontal shift using the trainer's correction rule |
| Contrast + brightness | 0.90 | Global exposure variation |
| BGR channel jitter | 0.65 | Per-channel gain/bias (white-balance drift) |
| Mixed lighting (sun/shadow split) | 0.55 | Soft sun-vs-shadow boundary across the frame |
| Diagonal shadow band | 0.35 | Angled shadow stripe |
| Curved curb distractor | 0.30 | Fake curved edge to resist false path cues |
| Polygon shadow | 0.25 | Hard shadow polygon |
| Glare | 0.12 | Radial bright spot |
| Gaussian noise | 0.35 | Sensor noise |
| Gaussian blur | 0.18 | Mild defocus |

- On top of that, a **shadow-stress bundle** (`apply_shadow_stress_augmentation`) fires with probability `--shadow-aug-probability` (default `0.85`). For `real` and `correction` sources that probability is multiplied by `1.25` (capped at 1.0), so real frames get even more shadow stress. The bundle itself randomly layers mixed lighting, diagonal shadow bands, tree-shadow dapple, sidewalk/road edge shadow, and patchy concrete texture.
- **CARLA domain randomization** (`apply_carla_domain_randomization`) fires only on `carla`-source frames, at `--carla-domain-randomize-probability` (default `0.70`): stronger contrast/brightness swings, channel jitter, texture, blur, and noise to shrink the sim-to-real gap.
- **HSV jitter** and **CLAHE** are available but default OFF (`--hsv-aug-probability 0.0`, `--clahe-aug-probability 0.0`).
- **Horizontal flip** defaults OFF (`--flip-aug-probability 0.0`). When enabled it mirrors the image and sets `steer = 180 - steer`.

## Why this choice

- The failures that matter on real sidewalks are lighting failures — shadow edges, dappled tree shade, low evening sun, sun/shade splits. So the augmentation budget is spent there, not on unrealistic distortions.
- Camera jitter applies a steering correction based on horizontal translation. This is an engineering approximation, not proof that every rotated or scaled view has a perfectly corrected physical command.
- Keeping augmentation in the trainer makes the transform implementation and flags recordable with each run. Reproduction also requires the code revision, seed, dataset snapshot, and complete command.

## The Flip Lesson

Horizontal flip is off by default. Mirroring can improve left/right balance, but it also assumes the scene and vehicle behavior remain valid after reflection. Sidewalk edges, curbs, driveways, and vehicle bias can violate that assumption. The trainer therefore leaves random flip at `0.0` unless a recorded experiment enables it; it also force-disables flip for `--model-version 2.3`.

## Previewing augmentations

`code/test_files/camera/preview_series3_augmentations.py` renders a labeled grid of augmented variants of one image using the exact trainer functions, so what you preview is what training sees:

```bash
python3 code/test_files/camera/preview_series3_augmentations.py \
  code/ai_models_datasets/series_3_and_4/sidewalkpilot_dataset/example.jpg \
  --output /tmp/series3_augmentations.jpg \
  --count 12 --columns 4 --source real
```

## Status note

The shadow-focused pipeline has now been used for Series 3 training, and v3.4 passed the July 13 shadow field comparison. That result supports the complete training/data iteration, not a causal claim that one augmentation alone produced the improvement. HSV/CLAHE remain off by default.

## Evidence to attach

- `code/test_files/camera/preview_series3_augmentations.py`
- `augment_image` (and the `apply_*` helpers) in the Series 3 trainer
- Example augmentation grid image
- Validation metrics with/without major augmentation settings

## Related pages

- `ai-and-models/training-pipeline/training-script.md`
- `data-governance/data-quality/lighting-coverage.md`
- `testing/failures/shadow-failures.md`
