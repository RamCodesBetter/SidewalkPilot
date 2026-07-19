# Augmentation Versus Fixed Preprocessing

This page records the decision to make the Series 3 model robust to lighting and
viewpoint through **randomized training-time augmentation**, rather than a fixed
inference-time preprocessing transform (like always running CLAHE on the car).

## Decision

Inference preprocessing stays minimal and fixed — raw BGR, resize, normalize. All the robustness work happens at **training
time**, in `augment_image(...)` and the dataset loader in
`code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`. Each training frame
is randomly perturbed, so the network sees multiple lighting/viewpoint
versions of the same scene. The intended effect is to reduce sensitivity to nuisance variation; it is not guaranteed. The main
augmentations and their default probabilities:

| Augmentation | Default prob | What it simulates |
|---|---:|---|
| Shadow stress (diagonal band / tree-dappled / edge shadows) | `0.85` bundle | hard sun shadows across the sidewalk |
| Brightness + contrast jitter | `0.90` | over/under-exposure, time of day |
| Camera jitter (small warp, angle carried into the label) | `0.75` | mounting/tilt variation |
| BGR channel jitter | `0.65` | color/white-balance drift |
| Mixed lighting | `0.55` | patchy sun/shade |
| CARLA domain randomization | `0.70` (sim samples) | closing the sim→real gap |
| Horizontal flip | opt-in (`--flip-aug-probability`) | mirror turns: `steer = 180 - steer` |
| HSV jitter / CLAHE as *augmentation* | `0.0` (off) | available but disabled by default |

The horizontal flip is a *label-aware* mirror — it flips the image and sets
`steer = 180.0 - steer` — which cheaply balances left vs right turns. HSV and
CLAHE are wired in as optional augmentations but default to probability `0.0`.

## Why Augmentation, Not a Fixed Transform

A fixed inference transform (e.g. "always CLAHE on the car") only reshapes the
input one way and must match training exactly. It doesn't teach the model to
handle the *range* of real conditions — and on my worst case, tree-dappled
shadows, a contrast transform can actually make the distractor sharper.

Randomized augmentation exposes the model to shadowed, dim, bright, tilted, and
color-shifted variants during training. Whether this transfers to a field condition must be
measured on the car:

- **v3.2 / v3.2b** were part of the shadow-focused iteration sequence. The current record
  does not preserve a controlled augmentation-only comparison against v3.1b, so it does not
  isolate augmentation as the cause of any difference.
- **Later evidence:** v3.3/v3.3b regressed in the July 13 field comparison despite promising offline changes. v3.4 handled every presented shadow case and became the field-selected baseline. This is evidence for testing augmentation changes on the car, not proof that all shadow conditions are solved.

Care point: aggressive augmentation can obscure useful image signal. The historical run
records do not isolate one augmentation parameter as the cause of a field regression, so
strength and probability remain experimental settings rather than settled facts.

## Runtime Preprocessing Contract

The camera captures OpenCV `BGR888`; current Series 3/4 inference keeps BGR, resizes, and
normalizes with `(x/255 - 0.5)/0.5`. Only legacy models 2.0 and 2.0b enable HSV-value
CLAHE. This version-specific exception preserves train/runtime parity. Applying CLAHE to a
checkpoint that was trained on raw BGR would silently change its input distribution, while
applying it universally could amplify hard shadow boundaries and add per-frame CPU work.

## Alternatives Considered

| Option | Pros | Cons |
|---|---|---|
| Fixed inference transform only (e.g. always CLAHE) | deterministic, one code path | doesn't teach the model the real range; parity trap; can sharpen distractors |
| No augmentation, just collect more raw data | cleanest labels | needs enormous, perfectly-balanced capture to cover all lighting |
| **Randomized training-time augmentation + minimal inference preprocessing (chosen)** | one model handles many conditions; cheap to expand; inference stays simple | too-strong aug can wash out signal; synthetic shadows ≠ real shadows (still need real data) |

## How to Know It Worked (Test Gate)

- Preview augmentation variants before a run with
  `code/test_files/camera/preview_series3_augmentations.py`.
- Compare hard-shadow field clips across versions (the v3.1b → v3.2b shadow study
  is the template); success = fewer shadow-driven edge drifts, not a lower MAE.
- Re-test the exact shadow cases for every promoted model. Series 4.0 completed a supervised comparison but produced no promotion; Series 4.1 has not reached that gate.

## Related Pages

- [Model Inference](../../autonomy-stack/camera-steering/model-inference.md)
- [Failures and Lessons](../../testing/failures/overview.md)
- [Next Steps](../../roadmap/next-steps.md)
