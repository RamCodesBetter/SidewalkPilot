# Field Evaluation Overview

Field evaluation checks behavior that an image-label report cannot measure:
Raspberry Pi 5–Jetson Orin Nano latency, steering smoothness, shadow response, mechanical drift,
operator takeovers, and LiDAR braking on the assembled vehicle.

## Offline Versus Field Evidence

The common evaluator writes `docs/steering_eval_current_labels.json` and
`docs/steering_model_report.pdf` for 52 checkpoints on a frozen 6,952-frame
Series 3/4 subset. Bal9 and turn metrics help reject center-collapsed candidates;
MAE, median error, and signed error add magnitude and bias context.

Those values do not select a field baseline by themselves. A model must load
through the live ONNX path, preserve manual response, and complete a
supervised field comparison under the condition it is intended to improve.

## Current Field Record

The July 13 comparison is an operator-observed, bounded field result:

- v3.4 handled every shadow case presented in that run and is the current
  field-selected baseline;
- v3.4b was slightly worse;
- v3.3 was worse than v3.2;
- v3.3b was much worse than v3.2b.

This record does not contain enough repeated-route quantitative measurements to
claim a universal success rate. In a later supervised v4.0 comparison, v4.0f was
viable and complementary with v3.4, v4.0g was worse, and the PC/PCF models echoed
prior steering predictions. The v4.1 correction models remain offline-only.

## Run Record

A reproducible field comparison should retain:

- Model version and artifact hash;
- Route, surface, lighting, weather, battery, and payload;
- Start/end time and distance;
- Takeover count and cause;
- Runtime CSV (nominal 10 Hz, 46 columns);
- Video/clip identifiers;
- AEB state and any LiDAR intervention;
- Pass, warning, or failure decision made before examining the next model.

The operator keeps the Xbox controller ready. Steering, gas, or brake input
cancels autonomy through `cancel_autonomous_mode()`.

## Related Pages

- [Model Retest Plan](../../testing/field-testing/model-retest-plan.md)
- [Manual Takeover Count](manual-takeover-count.md)
- [Bal9](../offline-evaluation/bal9.md)
