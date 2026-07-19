# Offline Evaluation Overview

Offline evaluation orders the checkpoints eligible for a supervised physical test. It is repeatable and cheaper than a field run, but it does not establish that a checkpoint is safe.

## Common Challenge Set

The current evaluator runs every model from v1.0 through v4.1c on the same **6,952-frame frozen Series 3/4 temporal validation subset**:

- D0702: 4,230 frames;
- D0707: 652 frames;
- D0712: 2,070 frames.

Series 1/2 frames are resized to 200x66 and decoded as direct steering regression. Series 3/4 frames are 320x180 and use their matching regression or hybrid decoder. This compares behavior on the same images and labels even though the architectures differ.

## Evaluator Outputs

`code/test_files/models/evaluate_sidewalkpilot_models.py` discovers all supported checkpoints and writes:

- `docs/steering_eval_current_labels.json`, containing overall, source, bucket, confusion, and selection metrics;
- `docs/steering_model_report.pdf`, a 23-page report with the class-balanced ranking, all-series MAE bars, per-model sections, and confusion matrices.

The JSON retains older Series 1/2 own-dataset scores under `historical_evaluation`. Historical metrics answer how those models were originally reported. Common metrics answer how all 52 behave on today's challenge set. The two contexts are labeled and never silently substituted.

## Why One Metric Is Not Enough

The challenge set has 4,741 ST frames and 2,211 non-ST frames. Overall exact accuracy or MAE is therefore strongly influenced by straight behavior. A useful steering model must preserve rare classes as well as the majority.

| Metric | Primary use |
|---|---|
| Bal9 | equal-weight class capability |
| Turn exact / +/-1 | turning behavior |
| ST exact | straight stability |
| MAE / median | numeric error magnitude |
| Signed error | directional bias |
| Confusion matrix | exact failure pattern |
| Per-source metrics | sensitivity to capture run/condition |

## Metric Definitions

- **MAE:** mean of `abs(predicted - target)` in degrees. It is easy to compare but can reward a center-biased model on a straight-heavy set.
- **Median AE:** the 50th percentile absolute error. It is less sensitive to a few extreme misses but can hide rare dangerous errors.
- **Max AE:** largest observed absolute error. It identifies an extreme sample but is unstable and should be investigated at the frame level.
- **Signed error:** mean of `predicted - target`. Positive means predictions trend toward larger/rightward values; negative means smaller/leftward values. Opposite errors can cancel.
- **Within-degree rates:** fraction of frames inside fixed numeric thresholds. These describe precision but not class balance.
- **Turn exact / +/-1:** exact steering-class agreement for non-straight targets, or agreement within one neighboring class.
- **ST exact:** exact class agreement for straight targets.
- **Bal9:** macro recall across the nine steering classes, giving every target class equal weight.

The confusion matrix supplies the evidence behind these summaries. A strong model should not concentrate all predictions in the straight column or systematically shift one direction.

## Offline and Field Evidence

Offline results can find collapse, bias, and promising candidates. They cannot reproduce tire load, servo hysteresis, network delay, a particular shadow angle, or compounding closed-loop mistakes. That limitation was visible in v4.0: PC and PCF ranked strongly offline but echoed their own earlier steering predictions on the car. v4.0f was viable but mixed against v3.4, so v3.4 remains the default.

The next model test begins only after v4.1 runtime integration and closed-loop bench replay. It should use v3.4 and v4.0f as controls while testing the six v4.1 correction models under the same route and conditions.

## Reproduce

On the evaluation workstation with ONNX Runtime GPU installed:

```bash
cd ~/rc_car_code
python -u \
  code/test_files/models/evaluate_sidewalkpilot_models.py \
  --device cuda --batch-size 256
```

See [Bal9](bal9.md), [Confusion Matrix](confusion-matrix.md), and [Offline vs Field](../comparisons/offline-vs-field.md).
