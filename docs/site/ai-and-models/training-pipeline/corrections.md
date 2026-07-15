# Corrections

Corrections documents how manually reviewed labels supplement or override the base dataset labels. A correction is how a specific field-test failure becomes an actionable training signal without rewriting a whole dataset. This page covers when a correction is allowed, how it overrides a base label, why Series 3 corrections must carry throttle, and how corrections are kept from silently corrupting training.

## How it works

- Correction files are loaded separately from dataset `labels.json` files, by `load_correction_items`. Each entry is tagged with the file it came from (`_correction_file`) so its image can be resolved relative to that file.
- The loader accepts three shapes: a list of objects, a `{"samples": [...]}` dict, or an image-to-label dict (converted to a list internally). A non-object entry is a hard error.
- **Override behavior:** before scanning a base root, the dataset collects every image path that appears in a correction file. When a base `labels.json` entry points at one of those images, the base label is skipped (`skipped base labels overridden by corrections`) so the correction is the only label that survives.
- **Series 3 requires throttle.** A correction is loaded with both `get_raw_steering` and `get_raw_throttle`; if either cannot be parsed the entry is counted as `bad` and dropped.
- **Weighting / repetition:** each correction entry has an optional `repeat` field (default `6`) — the sample is inserted that many times — and correction samples also carry a higher source weight in the sampler (`correction_sample_weight`, default `3.0`). Both push rare-but-important cases into training more often.

## Why this choice

- Corrections make field-test failures fixable without regenerating datasets: relabel the frames that failed, drop them in a correction file, and they win over the base label.
- Keeping corrections in JSON keeps the label history reviewable — you can see exactly which frames were overridden and to what.
- Series 3 requires throttle on corrections because a steering-only correction would teach half the control behavior and quietly bias throttle.

## Rules at a glance

| Item | Rule |
|---|---|
| Format | List, `{"samples": [...]}`, or image-to-label dict (loader normalizes all three) |
| Required fields (Series 3) | image reference, `steering`, `throttle` |
| Missing/unparseable throttle | Entry dropped as a bad label |
| Base-label override | Any base image also present in a correction file is skipped |
| Repeat | `repeat` field (default 6) duplicates the sample that many times |
| Source weight | `correction` weight (default 3.0) is higher than real (2.0) or CARLA (0.6) |

## What should become a correction vs new data

- A **correction** fits a bounded, identifiable failure: a handful of frames the model got wrong that you can confidently relabel (e.g. a specific lamppost or shadow band that flipped the steering).
- **New data collection** fits a *distribution* gap — a whole class of situations (e.g. mid-right turns in shadow) the dataset barely contains. You cannot correction-weight your way out of a missing bucket; over-repeating a few frames just overfits them.

## Status note

The current Series 3/4 directory has no `steering_corrections.json`. Its 81,237
base records live in `sidewalkpilot_dataset/labels.json`. Optional correction support
is implemented in the Series 3 trainer. The Series 4 temporal engine currently has no
correction-file argument and trained from the unchanged base labels. A release should
claim correction use only when the exact trainer command and log identify it.

## Evidence to attach

- `load_correction_items` in the trainer
- `SteeringDataset` correction-loading + override logic
- Example correction JSON
- Training log showing correction sample count

## Related pages

- `data/corrections-json.md`
- `data-governance/labeling/relabel-review.md`
- `ai-and-models/training-pipeline/source-weights.md`
