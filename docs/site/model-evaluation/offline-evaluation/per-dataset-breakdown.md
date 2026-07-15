# Per-Source Breakdown

An overall score can hide a model that works on one collection run and fails on another.
The evaluator therefore stores a `by_dataset` block for each checkpoint.

## Current Report Sources

The common 6,952-frame Series 3/4 challenge set contains:

| Source | Anchors |
|---|---:|
| D0702_16 | 4,230 |
| D0707_16 | 652 |
| D0712_16 | 2,070 |

Each source block contains the same numeric metrics as the overall block, including count,
MAE, median and maximum absolute error, signed error, within-degree counts, prediction mean,
and target mean.

The JSON also retains the original 13-source, 2,224-image Series 1/2 correction-set
breakdown under each early model's `historical_evaluation`. Those blocks document the early
project but are not used for top-level cross-series ranking.

## Why It Matters

The shared set is not uniform. Different days contain different turns, lighting, framing,
and routes. A model with acceptable overall Bal9 or MAE can still have one source with a
large signed bias or error tail. That pattern identifies where to inspect confusion rows and
which physical case to repeat.

Source differences are evidence of sensitivity, not an automatic root-cause diagnosis.
The source key alone does not prove that lighting, route geometry, or labeling caused the
difference; that conclusion needs the associated images and run notes.

## Source

`code/test_files/models/evaluate_sidewalkpilot_models.py` assigns D-codes from run/image timestamps
and writes the full breakdown to `docs/steering_eval_current_labels.json`.

## Related Pages

- `model-evaluation/offline-evaluation/overview.md`
- `model-evaluation/offline-evaluation/signed-error.md`
- `testing/field-testing/field-logs.md`
