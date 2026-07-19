# Model Retest Plan

Offline evaluation decides what is worth driving. A fixed supervised route decides what is worth promoting.

## Current Candidates

The v4.0 test is complete. v4.0f was viable and complementary with v3.4, while v4.0g was worse. v4.0p/r/a/c repeatedly echoed earlier predictions and were rejected even though several ranked strongly offline.

After v4.1 integration and bench replay, use this order to control route and battery drift:

1. v3.4 baseline;
2. v4.0f control;
3. v4.1p;
4. v4.1r;
5. v4.1a;
6. v4.1c;
7. v4.1f;
8. v4.1g;
9. Optional v3.4 repeat.

Skip any v4.1 history model that repeats the v4.0 steering-echo failure in bench replay. Offline metrics do not override that gate.

## Procedure

1. Record branch/commit, ONNX hash, model version, AEB state, steering calibration, battery state, route, lighting, and weather.
2. Confirm the intended version loaded on Jetson Orin Nano and appears on the dashboard.
3. Drive ordinary left and right turns plus the known hard-shadow cases.
4. Record every takeover and reason.
5. For PC/PCF, watch for steering echo, drift, lag, or oscillation after large turns, model switches, and manual periods.
6. Repeat the baseline if conditions changed during the session.
7. Mark pass, mixed, or fail; do not infer missing details after the run.

## Verdict Rules

- Pass: no new safety-critical failure, acceptable smoothness, and equal/better route behavior than v3.4.
- Mixed: improves one condition while regressing another; retain as research evidence, not default.
- Fail: more takeovers, road-edge risk, unstable steering, stale inference, or a failure absent from v3.4.

See [Field Model Selection](../../runbooks/field-test-day/model-selection.md) and [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md).
