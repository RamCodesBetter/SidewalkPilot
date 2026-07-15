# Model Retest Plan

Offline evaluation decides what is worth driving. A fixed supervised route decides what is worth promoting.

## Current Candidates

Use this order to compare temporal designs while controlling route/battery drift:

1. v3.4 baseline;
2. v4.0p;
3. v4.0r;
4. v4.0a;
5. v4.0c;
6. v3.4b;
7. v4.0f;
8. v4.0g;
9. Optional v3.4 repeat.

v4.0p leads common-set Bal9/turn metrics, v4.0c leads MAE/median, and v4.0r leads ST exact. None is field-proven.

## Procedure

1. Record branch/commit, ONNX hash, model version, AEB state, steering calibration, battery state, route, lighting, and weather.
2. Confirm the intended version loaded on Jetson Orin Nano and appears on the dashboard.
3. Drive ordinary left and right turns plus the known hard-shadow cases.
4. Record every takeover and reason.
5. For PC/PCF, watch for autoregressive drift, lag, or oscillation after model switches and manual periods.
6. Repeat the baseline if conditions changed during the session.
7. Mark pass, mixed, or fail; do not infer missing details after the run.

## Verdict Rules

- Pass: no new safety-critical failure, acceptable smoothness, and equal/better route behavior than v3.4.
- Mixed: improves one condition while regressing another; retain as research evidence, not default.
- Fail: more takeovers, road-edge risk, unstable steering, stale inference, or a failure absent from v3.4.

See [Field Model Selection](../../runbooks/field-test-day/model-selection.md) and [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md).
