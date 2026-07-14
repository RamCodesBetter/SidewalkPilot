# Series 4 Plan

Series 4 is a parallel architecture research track. It starts from the field-proven Series 3.4 baseline without replacing it.

## Status

No Series 4 checkpoint exists yet. No `4.x` option is present in the live controller or Jetson model list. The initial scaffold is `code/ai_models_datasets/series_4/SERIES4_PLAN.md`.

## Design Rule

The first experiment must state one architectural hypothesis before code is copied or training begins. Dataset, split, evaluation, and deployment changes must not be mixed into the same experiment unless they are the hypothesis being tested.

The compatibility baseline is `320x180` BGR input, absolute steering labels, useful-range throttle labels (`0..1` maps physical `55..100%`), time-segment validation, ONNX deployment on Jetson, and a fixed v3.4 replay. The current 19-output hybrid head can be retained or replaced, but trainer, loss, evaluator, export, and Jetson decoding must agree on the contract.

## Promotion Evidence

Series 4 must beat v3.4 on turn recall and the fixed field shadow route, not only aggregate MAE. It must also satisfy Jetson latency, output-shape, ONNX-load, command-freshness, and center-corridor AEB tests before becoming selectable in production.

See [Steering Model Series](../../autonomy-stack/camera-steering/series-differences.md) and [Shadow Robustness](../../model-evaluation/field-evaluation/shadow-robustness.md).
