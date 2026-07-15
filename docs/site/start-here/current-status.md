# Current Status

Last updated: **July 15, 2026**.

## Working Baseline

- **Field-selected steering model:** v3.4, running as FP32 ONNX on the Jetson Orin Nano.
- **Field result:** v3.4 completed every harsh-shadow case presented in the July 13 comparison and ranked above v3.4b, v3.3, and v3.3b.
- **Series 4:** all three temporal experiments completed 25 epochs. Six ONNX checkpoints exist and are supported by the live Raspberry Pi 5/Jetson Orin Nano model selector, but none has been field-tested or promoted over v3.4.
- **Steering calibration:** `+12D` center trim, normalized PCA9685 center offset `0.133333`, and physical center command near 102 degrees.
- **LiDAR connection:** FHL-LD19 through CP2102 USB serial. The runtime prefers its stable `/dev/serial/by-id/` path and normally falls back to `/dev/ttyUSB0`; scan processing is independent from Jetson Orin Nano inference.
- **LiDAR control:** one center safety corridor. It can reduce throttle or hard-brake, but it never steers.
- **AEB toggle:** gates every LiDAR throttle/brake intervention in manual and autonomous modes. Telemetry remains visible while intervention is disabled.
- **Dashboard:** Zero 2 W plus one Waveshare 64x32 HUB75 panel over a dedicated USB network. There is no current MAX7219 display or Wi-Fi telemetry fallback.
- **Control responsiveness:** in one physical retest with the Jetson Orin Nano powered off, the previously observed periodic control pauses were absent after network, file-scan, and temperature work was removed from the manual-control path. This is a bounded retest result, not a latency benchmark.

## Series 4 Result

The controlled comparison kept the same 81,237-image real dataset, deterministic split procedure, visual backbone, nine steering buckets, augmentation policy, and 25-epoch length. Only the temporal contract changed.

| Run | Contract | Final | Best-validation | Shared-eval result |
|---|---|---|---|---|
| `4.0pr` | image + previous 3 targets -> current | `4.0p` | `4.0r` | `4.0p` has the highest Bal9 and turn scores |
| `4.0fg` | image -> current + next 3 targets | `4.0f` | `4.0g` | weakest Series 4 pair on turn metrics |
| `4.0ac` | image + previous 3 targets -> current + next 3 | `4.0a` | `4.0c` | close to PC; `4.0c` has the lowest MAE |

All 46 checkpoints from Series 1 through Series 4 were rerun on the same **6,952-frame frozen Series 3/4 challenge subset**. The leading class-balanced candidate is `4.0p`: Bal9 34.5%, turn exact 32.1%, turn within one bucket 65.9%, straight exact 67.7%, and MAE 12.396 degrees. This is offline evidence, not a field verdict.

The next physical comparison order is v3.4 baseline, then `4.0p`, `4.0r`, `4.0a`, `4.0c`, v3.4b, `4.0f`, and `4.0g`. Repeating v3.4 at the end would help reveal route or lighting drift during the test.

## LiDAR Motion Policy

| Center distance | Action |
|---|---|
| At least 1.65 m | No LiDAR throttle limit |
| 1.65 m to 1.25 m | Reduce reference throttle linearly from 100% to 60% |
| 1.25 m to 1.05 m | Hold 60% reference throttle |
| At or below 1.05 m | Hard brake |

The 60% value is in the reference moving range. It maps to 82% physical PWM because commands at or below the measured 55% dead-zone boundary do not move this car. Saved labels use the absolute physical fraction (`0.82` for 82%), not the reference scale.

## Immediate Validation Needed

1. Run the center-corridor AEB test with AEB off and on, recording distance, action, and pass/fail evidence.
2. Field-test the eight-model sequence above on the same normal-turn and harsh-shadow route.
3. Record route, time, lighting, artifact hash, takeover count, and linked clips for every candidate.
4. Publish Series 4 model repositories only after cards can state an honest field result.

Do not treat an enabled AEB indicator as proof that LiDAR data is fresh. An empty, stale, or disconnected scan may produce no obstacle intervention; sensor health must be checked separately.

## Evidence Gaps

- The July 13 model comparison lacks a formal route identifier, weather record, takeover count, and linked video clips.
- Current LiDAR behavior has automated tests but needs a saved physical pass/fail record after the latest policy change.
- Series 4 has offline results and runtime support but no physical-car verdict.
- The current system has no claim of unattended operation or unrestricted pedestrian handling.

## Key Files

- `code/controller/current/rc_car_app/jetson_inference_server.py`: Series 1-4 ONNX loading, Series 4 history state, horizon-0 decoding, and CUDA provider selection.
- `code/controller/current/rc_car_app/runtime.py`: controller loop, AEB gating, arbitration, and motor application.
- `code/controller/current/rc_car_app/vision.py`: all 46 selectable checkpoint names and the v3.4 default.
- `code/ai_models_datasets/series_3_and_4/series_4_common.py`: shared PC/CF/PCF architecture and training engine.
- `code/test_files/models/evaluate_sidewalkpilot_models.py`: common-dataset evaluator.
- `docs/steering_model_report.pdf`: 22-page all-series comparison report.
- `docs/steering_eval_current_labels.json`: machine-readable results and historical S1/2 blocks.

Next: preserve a physical AEB result, run the ordered Series 4 field comparison, and promote a new model only if it improves real driving over v3.4.
