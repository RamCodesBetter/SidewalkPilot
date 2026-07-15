# Historical Metrics Policy

Metrics are stored with their dataset and evaluator context. A value produced on
one dataset is not silently compared with a value produced on another.

## Current Common Report

`code/test_files/evaluate_sidewalkpilot_models.py` adapts all 46 checkpoints to
their matching input/output contracts and evaluates them on the same frozen
6,952-frame Series 3/4 challenge subset. It writes:

- `docs/steering_eval_current_labels.json`;
- `docs/steering_model_report.pdf`.

The report records Bal9, turn exact, turn +/-1, ST exact, MAE, median absolute
error, signed error, class counts, and confusion matrices. Series 1/2 historical
own-dataset results are retained in a separately labeled JSON block; they are not
substituted for common-set values.

## Selection Rule

No one offline metric selects a field model. MAE and median error quantify
absolute error, signed error exposes directional bias, and the class/turn metrics
expose center collapse. Bal9 gives every nonempty steering class equal recall
weight. The physical field test remains the final promotion gate.

The `b` suffix means the trainer-selected validation checkpoint: validation loss for Series 1/2 and steering MAE for the current Series 3/4 trainers. It does not
mean best physical driver. Final and best artifacts are both retained so the
validation objective can be compared with field behavior.

## Provenance Rule

Every reported value should retain:

- Model artifact and hash when available;
- Architecture adapter;
- Dataset revision and subset identity;
- Evaluator commit;
- Training command/W&B run when making a training-history claim;
- Field-test date and conditions when making a driving claim.

## Related Pages

- [Bal9](../../model-evaluation/offline-evaluation/bal9.md)
- [MAE Versus Turn Capability](../../model-evaluation/comparisons/mae-vs-turn-capability.md)
- [B Checkpoints](../design-decisions/b-checkpoints.md)
