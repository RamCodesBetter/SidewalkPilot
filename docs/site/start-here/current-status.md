# Current Status

Last updated: **July 18, 2026**.

## Working Baseline

- **Field-selected steering model:** v3.4, running as FP32 ONNX on Jetson Orin Nano.
- **Field result:** v3.4 completed every harsh-shadow case presented in the July 13 comparison and ranked above v3.4b, v3.3, and v3.3b.
- **Series 4.0 result:** `4.0f` was viable and produced complementary outcomes versus v3.4. The history-input models `4.0p/r/a/c` repeated prior predictions and were rejected.
- **Series 4.1 status:** three correction runs completed 25 epochs and exported six ONNX models. They are not yet in the live model selector and have not been field-tested.
- **Steering calibration:** `+17D` center trim. Steering output is mapped through the calibrated logical-to-servo conversion before the PCA9685 command.
- **LiDAR connection:** FHL-LD19 through a CP2102 UART-to-USB adapter. The runtime prefers its stable `/dev/serial/by-id/` path and normally falls back to `/dev/ttyUSB0`.
- **LiDAR control:** one center safety corridor. With AEB enabled it can reduce throttle or hard-brake, but it does not steer.
- **AEB toggle:** gates LiDAR throttle/brake intervention in manual and autonomous modes. LiDAR telemetry remains visible while intervention is disabled.
- **Dashboard:** Zero 2 W plus one Waveshare 64x32 HUB75 panel over a dedicated USB network. There is no current MAX7219 display or Wi-Fi telemetry fallback.
- **Control responsiveness:** one physical retest with Jetson Orin Nano powered off no longer showed the earlier periodic pauses after blocking background work was removed from the controller path. This is a bounded observation, not a worst-case latency measurement.

## Model State

| Group | Current conclusion |
|---|---|
| v3.4 | live field-selected baseline |
| `4.0f` | viable comparison model; not clearly better than v3.4 |
| `4.0g` | worse than `4.0f` in the supervised comparison |
| `4.0p/r/a/c` | rejected because predictions echoed prior steering in closed-loop driving |
| `4.1p/r/f/g/a/c` | trained, exported, and common-set evaluated; runtime integration and field tests required |

The 4.0 failure is an important engineering result. Open-loop metrics favored several PC/PCF checkpoints, but the car exposed an autoregressive history failure that the image-by-image report could not reveal. Series 4.1 changes history representation, training losses, and checkpoint selection to address that specific failure without collecting new images.

## LiDAR Motion Policy

| Center distance | Action when AEB is enabled |
|---|---|
| At least 1.65 m | No LiDAR throttle limit |
| 1.65 m to 1.25 m | Reduce reference throttle linearly from 100% to 60% |
| 1.25 m to 1.05 m | Hold 60% reference throttle |
| At or below 1.05 m | Hard brake |

The 60% value is in the reference moving range. It maps to 82% physical PWM because commands at or below the measured 55% dead-zone boundary do not move this car. Saved throttle labels use the absolute physical fraction, not the reference scale.

## Immediate Validation Needed

1. Preserve a physical pass/fail record for center-corridor slowdown and emergency braking with AEB off and on.
2. Integrate selected 4.1 signatures into the live Jetson Orin Nano selector and verify PC/PCF history behavior before driving.
3. Compare v3.4, `4.0f`, and selected 4.1 candidates on the same normal-turn, shadow, and obstacle cases.
4. Record route, lighting, model SHA-256, takeover reason, CSV log, and linked video for each candidate.

An enabled AEB indicator does not prove that LiDAR data is fresh. A stale or disconnected scan may produce no intervention, so sensor health must be checked separately.

## Key Files

- `code/controller/current/rc_car_app/jetson_inference_server.py`: ONNX loading, signature inspection, history state, horizon-0 decoding, and CUDA provider selection.
- `code/controller/current/rc_car_app/runtime.py`: controller loop, AEB gating, control arbitration, and motor/steering output.
- `code/controller/current/rc_car_app/vision.py`: selectable live model names and the v3.4 default.
- `code/ai_models_datasets/series_3_and_4/series_4_common.py`: shared PC/CF/PCF architecture and training engine.
- `code/test_files/models/evaluate_sidewalkpilot_models.py`: common challenge-set evaluator.
- `docs/steering_model_report.pdf`: generated all-series comparison report.
- `docs/steering_eval_current_labels.json`: machine-readable results.

Next: integrate only the 4.1 candidates worth driving, replay the known steering-echo cases, and use physical behavior rather than MAE alone for promotion.
