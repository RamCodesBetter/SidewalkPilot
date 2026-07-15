# Steering Model PDF

`docs/steering_model_report.pdf` is the current generated comparison of every SidewalkPilot
steering checkpoint from v1.0 through v4.0c.

## What It Contains

The current report includes:

- One common 6,952-frame challenge-set ranking for all 46 checkpoints;
- A separate historical Series 1/2 evaluation on 2,224 correction-set images;
- Chronological growth tables for each model series;
- Green-to-red metric cells for Bal9, turn exact, turn +/-1, ST exact, MAE, median error,
  and signed error;
- All-series MAE bar graphs;
- Per-model detail tables and source-run breakdowns;
- Nine-class confusion matrices for the latest Series 3/4 candidates;
- Explicit notes about field evidence, source provenance, throttle scope, and the
  hold-last baseline.

The common challenge set is necessary because Series 1/2 and Series 3/4 have different
native datasets and input contracts. Resizing the same challenge images for each family
does not make the architectures identical, but it does place their current steering
behavior against the same targets.

## Reading the Ranking

Bal9 is macro recall across the nine steering classes. It gives each nonempty class equal
weight, so 4,741 straight targets cannot dominate the score. Turn exact and turn +/-1 focus
on the 2,211 non-straight targets. ST exact measures straight recall. MAE and median report
numeric distance from the target, while signed error exposes left/right bias.

No single column proves a model is safe or best. The report is an offline screening tool.
The current result places v4.0p first by Bal9 and v4.0c first by shared-set MAE, while v3.4
remains the field-selected model based on the July 13 comparison.

## Generation

The evaluator is:

```text
code/test_files/models/evaluate_sidewalkpilot_models.py
```

Run it from the repository root:

```bash
/home/rsabavat/.gpu-env/bin/python -u \
  code/test_files/models/evaluate_sidewalkpilot_models.py \
  --device cuda --batch-size 256
```

The evaluator writes JSON first and then renders the PDF. A wrong value must be corrected in
the labels, decoder, metric code, or report code and regenerated; the PDF should never be
edited by hand.

## Scope Limits

- The report evaluates steering only. Series 3's throttle output is not used for selection,
  and Series 4 removes throttle prediction.
- Offline inference does not reproduce closed-loop error accumulation, tire load, steering
  hysteresis, network delay, or all outdoor lighting.
- Historical checkpoint source mixes are unknown unless preserved run evidence proves them.
- Series 4 is not field-validated yet.

## Related Pages

- `publishing/reports.md`
- `model-evaluation/offline-evaluation/overview.md`
- `model-evaluation/comparisons/offline-vs-field.md`
