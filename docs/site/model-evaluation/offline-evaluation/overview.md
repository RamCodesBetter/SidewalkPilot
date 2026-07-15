# Offline Evaluation Overview

Offline evaluation orders the checkpoints eligible for a supervised physical test. It is repeatable and cheaper than a field run, but it does not establish that a checkpoint is safe.

## Common Challenge Set

The current evaluator runs every model from v1.0 through v4.0c on the same **6,952-frame frozen Series 3/4 temporal validation subset**:

- D0702: 4,230 frames;
- D0707: 652 frames;
- D0712: 2,070 frames.

Series 1/2 frames are resized to 200x66 and decoded as direct steering regression. Series 3/4 frames are 320x180 and use their matching regression or hybrid decoder. This compares behavior on the same images and labels even though the architectures differ.

## Evaluator Outputs

`code/test_files/evaluate_sidewalkpilot_models.py` discovers all supported checkpoints and writes:

- `docs/steering_eval_current_labels.json`, containing overall, source, bucket, confusion, and selection metrics;
- `docs/steering_model_report.pdf`, a 22-page report with the class-balanced ranking, all-series MAE bars, per-model sections, and confusion matrices.

The JSON retains older Series 1/2 own-dataset scores under `historical_evaluation`. Historical metrics answer how those models were originally reported. Common metrics answer how all 46 behave on today's challenge set. The two contexts are labeled and never silently substituted.

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

## Offline and Field Evidence

Offline results can find collapse, bias, and promising candidates. They cannot reproduce tire load, servo hysteresis, network delay, a particular shadow angle, or compounding closed-loop mistakes. v3.4 remains the field-selected baseline because it won the recorded field comparison even though newer Series 4 models lead offline.

The next field test starts with v3.4 as a control and tests `4.0p`, `4.0r`, `4.0a`, `4.0c`, v3.4b, `4.0f`, and `4.0g` in that order.

## Reproduce

On the evaluation workstation with ONNX Runtime GPU installed:

```bash
cd ~/rc_car_code
/home/rsabavat/.gpu-env/bin/python -u \
  code/test_files/evaluate_sidewalkpilot_models.py \
  --device cuda --batch-size 256
```

See [Bal9](bal9.md), [Confusion Matrix](confusion-matrix.md), and [Offline vs Field](../comparisons/offline-vs-field.md).
