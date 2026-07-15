# Optional Correction Files

The trainers can accept a separate correction file so reviewed labels can
override selected base rows without rewriting an immutable dataset snapshot.
This is a supported mechanism, not a claim that every training run used it.

## Current repository state

- Series 1/2 uses its checked-in `steering_corrections.json` as the primary
  historical label list.
- The current Series 3/4 dataset uses
  `sidewalkpilot_dataset/labels.json` as its primary label source.
- No `steering_corrections.json` is checked into the current Series 3/4
  directory.
- A Series 3/4 run used corrections only if its saved command or run log shows
  one or more `--corrections` paths and nonzero correction counts.

## Series 3/4 capability

`load_correction_items()` accepts:

- A list of `{image, steering, throttle, ...}` objects;
- A `{"samples": [...]}` object; or
- An image-to-label mapping.

When a supplied correction resolves to the same image as a base label, the base
row is skipped and the correction is loaded. Its optional `repeat` defaults to
`6`, and source `correction` receives the configured correction source weight
(default `3.0`) in the sampler. These settings make a small correction set
influential, so they must be recorded with the run.

## Why keep the capability

A correction file can preserve an immutable published snapshot while making a
small, reviewable experiment possible. It is also easy to misuse: repetition and
source weighting can overemphasize a bad edit. Corrections must describe the
desired logical steering label, never hardware trim or servo compensation.

## Evidence required for a correction run

1. Save the exact correction file and hash.
2. Preserve the training command and W&B configuration.
3. Check the printed `corrections used`, `missing`, `bad`, and
   `skipped base labels overridden` counts.
4. Re-evaluate the complete checkpoint on the same challenge subset.
5. Repeat the relevant physical route before promotion.

## Related pages

- [Corrections](../../ai-and-models/training-pipeline/corrections.md)
- [Relabel Review](../../data-governance/labeling/relabel-review.md)
- [Active Label Set](../../data-governance/dataset-versioning/active-label-set.md)
