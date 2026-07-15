# Training and Evaluation Metrics

SidewalkPilot does not choose a steering model from one loss or one accuracy number. The dataset is dominated by straight driving, so the metric set must expose whether a low-error model has quietly stopped turning.

## During Training

Series 3 and 4 log two levels of data to Weights & Biases.

**Step metrics** show whether optimization is healthy:

- Total, class, and offset loss;
- Learning rate;
- `grad_norm`, the L2 norm of all parameter gradients before clipping;
- Predicted steering range for the batch;
- Batch progress and elapsed time.

`grad_norm` is not a quality score. A finite, varying value shows that gradients are flowing. A value near zero for long periods can indicate stalled learning; repeated large spikes can indicate unstable updates. The trainer clips gradients to 1.0 after measuring the norm, so the graph records the pressure before clipping.

**Epoch metrics** evaluate the complete frozen validation split:

- Current-target MAE, median absolute error, and signed error;
- Bal9;
- Turn exact and turn +/-1;
- Straight exact;
- Prediction and target counts for every steering class;
- Per-class recall;
- Per-horizon MAE for Series 4 CF/PCF;
- Hold-last MAE for history experiments.

## Nine Steering Classes

| Class | Degrees |
|---|---:|
| HL | 0-45 |
| L | 45-60 |
| L+ | 60-75 |
| SL | 75-85 |
| ST | 85-95 |
| SR | 95-105 |
| R | 105-120 |
| R+ | 120-135 |
| HR | 135-180 |

The left edge is inclusive and the right edge is exclusive, except the last class includes 180.

## Selection Panel

| Metric | Calculation | What it catches |
|---|---|---|
| Bal9 | mean of the nine per-class exact recalls | dead rare classes hidden by straight majority |
| Turn exact | exact-bucket recall over every non-ST target | whether turns land in the right class |
| Turn +/-1 | recall allowing one neighboring class | directionally useful near misses |
| ST exact | exact recall for 85-95 targets | straight stability |
| MAE | mean `abs(pred-target)` | average numeric error |
| Median AE | median `abs(pred-target)` | typical error without tail domination |
| Signed | mean `pred-target` | systematic left/right bias |
| Hold-last MAE | mean `abs(previous_target-current_target)` | no-model temporal baseline |

Hold-last MAE answers: “If I ignored the image and repeated the most recent known target, how wrong would I be?” On the shared challenge subset it is 11.199 degrees. A temporal model should not be praised merely for approaching that baseline; it must also improve class balance and real field behavior.

## Why MAE Is Secondary

There are 4,741 straight targets and 2,211 turn targets in the 6,952-frame challenge set. Predicting center frequently can lower MAE and median error while missing the steering events that keep the car on the sidewalk. v3.4b illustrates the pattern: lower MAE than v3.4, but weaker turn metrics and worse physical behavior.

The rule is not “ignore MAE.” It is “do not let MAE hide class collapse.” Bal9 and turn recall gate the model; MAE, signed error, smoothness, and field behavior complete the decision.

## Common Evaluator

`code/test_files/models/evaluate_sidewalkpilot_models.py` evaluates all 46 checkpoints on the same 6,952-frame Series 3/4 validation subset. It adapts input resolution and output decoding by series, writes `docs/steering_eval_current_labels.json`, and generates `docs/steering_model_report.pdf`.

Older Series 1/2 own-dataset results are retained under each model's `historical_evaluation` block. They remain useful for historical reproduction but are not mixed into the common ranking.

See [Bal9](../../model-evaluation/offline-evaluation/bal9.md), [MAE vs Turn Capability](../../model-evaluation/comparisons/mae-vs-turn-capability.md), and [Model Selection Rubric](../../model-evaluation/comparisons/model-selection-rubric.md).
