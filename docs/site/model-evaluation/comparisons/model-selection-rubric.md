# Model Selection Rubric

A checkpoint moves through three gates: artifact validity, offline capability, and physical-car behavior. Passing one gate does not imply passing the next.

## Gate 1: Artifact

- Checkpoint and ONNX file load;
- Input names and shapes match the runtime contract;
- Output shape and decoder agree;
- CUDA provider is active on Jetson Orin Nano;
- Inference is fresh and does not block manual control;
- Temporal state resets safely on model switch/reconnect.

## Gate 2: Offline

Read the metric panel in this order:

1. Bal9 and nine-class confusion matrix: no dead or collapsed steering classes.
2. Turn exact and turn +/-1: enough turn capability to justify a field test.
3. ST exact: enough straight stability to avoid needless oscillation.
4. Signed error: no severe directional bias.
5. MAE and median: numeric precision among models that passed the class gate.
6. Per-source behavior and hold-last baseline: no result explained by one easy run or simple temporal persistence.

## Gate 3: Field

- Same route, direction, lighting cases, and speed policy;
- Baseline model first and, ideally, repeated last;
- Takeover count and reason;
- Shadow following, missed turns, curb/grass approach, and oscillation;
- Inference rate and stale-command behavior;
- AEB state and any safety interventions;
- Linked video and CSV evidence.

The field-selected model remains the live baseline even if another checkpoint has lower MAE. That happened when v3.4 beat v3.4b.

## Current Decision

- Field-selected baseline: v3.4.
- First challenger: `4.0p` because it leads Bal9 and turn metrics.
- Lowest-error challenger: `4.0c`.
- Not yet eligible for promotion: every Series 4 checkpoint, pending field evidence.

The final-vs-best suffix is descriptive, not a deployment rule. Test both when their tradeoff is meaningful.
