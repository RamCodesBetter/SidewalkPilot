# Model Selection Rubric

A checkpoint moves through three gates: model validity, offline capability, and physical-car behavior. Passing one gate does not imply passing the next.

## Gate 1: Model Validity

- The deployable model file loads: PTH for Series 1/2 or ONNX for Series 3/4.
- Input names and shapes match the intended model contract, including PC, CF, or PCF where applicable.
- Output shape and steering decoder agree.
- Inference uses the expected Jetson Orin Nano GPU path: PyTorch CUDA for Series 1/2 or ONNX Runtime CUDA for Series 3/4.
- Predictions are fresh and manual control remains responsive.
- PC/PCF history starts from recent manual steering when autonomy begins and resets on model changes or reconnects.

## Gate 2: Offline Evaluation

Read the metric panel in this order:

1. Bal9 and the nine-class confusion matrix: no dead or collapsed steering classes.
2. Turn exact and turn +/-1: enough turn capability to justify a field test.
3. ST exact: enough straight stability to avoid needless oscillation.
4. Signed error: no severe directional bias.
5. MAE and median error: numeric precision among models that passed the class checks.
6. Per-source behavior and the hold-last baseline: no result explained by one easy run or simple steering persistence.

## Gate 3: Physical-Car Comparison

- Use the same route, direction, lighting cases, and speed policy.
- Run the baseline first and, when practical, repeat it last.
- Record takeover count and reason.
- Watch for shadow following, missed turns, curb or grass approach, oscillation, and repeated steering.
- Verify inference rate and stale-prediction handling.
- Record AEB state and any safety interventions.
- Preserve video and CSV evidence.

The field-selected model remains the baseline even if another checkpoint has lower MAE. v3.4 beat v3.4b despite v3.4b's lower offline MAE. The 4.0 comparison reinforced the same lesson: history-based 4.0 models ranked strongly offline but repeated earlier predictions on the car.

## Current Decision

- **Field-selected baseline:** v3.4.
- **Viable 4.0 comparison model:** `4.0f`; it showed complementary wins and failures against v3.4, not a clear promotion case.
- **Rejected 4.0 history models:** `4.0p`, `4.0r`, `4.0a`, and `4.0c` because of closed-loop steering echo.
- **Lower-ranked 4.0 CF checkpoint:** `4.0g`, which was worse than `4.0f` in the supervised comparison.
- **Pending:** all six 4.1 checkpoints have common-set results but still require runtime integration, closed-loop replay, and physical testing.

Final-versus-best naming is descriptive, not a deployment rule. Both checkpoints must pass the same gates.
