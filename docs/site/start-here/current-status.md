# Current Status

Last updated: **July 18, 2026**.

## Working Baseline

- **Field-selected steering model:** v3.4, running as FP32 ONNX on the Jetson Orin Nano.
- **Field result:** v3.4 completed every harsh-shadow case presented in the July 13 comparison and ranked above v3.4b, v3.3, and v3.3b.
- **Series 4.0:** six ONNX models are runtime-supported and were field-tested. Image-only v4.0f was viable but mixed against v3.4; v4.0g was worse; the four PC/PCF models echoed earlier predictions and were rejected.
- **Series 4.1:** six corrected ONNX models are trained and evaluated offline. They are not yet in the live selector and have not been driven.
- **Steering calibration:** `+17°` center trim, normalized PCA9685 center offset `0.188889`, and physical center command near 107 degrees.
- **LiDAR connection:** FHL-LD19 through a CP2102 UART-to-USB Adapter. The runtime prefers its stable `/dev/serial/by-id/` path and normally falls back to `/dev/ttyUSB0`; scan processing is independent from Jetson Orin Nano inference.
- **LiDAR control:** one center safety corridor. It can reduce throttle or hard-brake, but it never steers.
- **AEB toggle:** gates every LiDAR throttle/brake intervention in manual and autonomous modes. Telemetry remains visible while intervention is disabled.
- **Dashboard:** Zero 2 W plus one Waveshare 64x32 HUB75 panel over a dedicated USB network. There is no current MAX7219 display or Wi-Fi telemetry fallback.
- **Control responsiveness:** in one physical retest with the Jetson Orin Nano powered off, the previously observed periodic control pauses were absent after network, file-scan, and temperature work was removed from the manual-control path. This is a bounded retest result, not a latency benchmark.

## Series 4 Results

The three v4.0 training experiments kept the same 81,237-image real dataset, deterministic split procedure, visual backbone, nine steering buckets, augmentation policy, and 25-epoch length. Only the temporal contract changed.

| Run | Contract | Final | Validation-selected | Shared-evaluation result |
|---|---|---|---|---|
| `4.0pr` | image + previous 3 targets -> current | `4.0p` | `4.0r` | `4.0p` has the highest Bal9 and turn scores |
| `4.0fg` | image -> current + next 3 targets | `4.0f` | `4.0g` | weakest Series 4 pair on turn metrics |
| `4.0ac` | image + previous 3 targets -> current + next 3 | `4.0a` | `4.0c` | close to PC; `4.0c` has the lowest MAE |

All 52 checkpoints from Series 1 through Series 4.1 were rerun on the same **6,952-frame frozen Series 3/4 challenge subset**. `4.0p` leads the class-balanced report at Bal9 34.5%, but its physical steering-echo failure demonstrates that this is an offline ranking rather than a field verdict.

The v4.1 trainers were changed in response to the steering-echo failure. Their new losses and history perturbations still require closed-loop replay and live integration before any physical comparison. v3.4 and v4.0f are the controls for that later test.

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
2. Integrate only the v4.1 models that pass closed-loop replay and signature checks.
3. Field-test those candidates against v3.4 and v4.0f on the same normal-turn and harsh-shadow route.
4. Record route, time, lighting, model file hash, takeover count, and linked clips for every candidate.

Do not treat an enabled AEB indicator as proof that LiDAR data is fresh. An empty, stale, or disconnected scan may produce no obstacle intervention; sensor health must be checked separately.

## Evidence Gaps

- The July 13 model comparison lacks a formal route identifier, weather record, takeover count, and linked video clips.
- Current LiDAR behavior has automated tests but needs a saved physical pass/fail record after the latest policy change.
- Series 4.0 has a bounded qualitative field verdict; Series 4.1 does not.
- The current system has no claim of unattended operation or unrestricted pedestrian handling.

## Key Files

- `code/controller/current/rc_car_app/jetson_inference_server.py`: Series 1/2 PyTorch and Series 3/4 ONNX loading, Series 4 history input, horizon-0 decoding, and GPU-provider selection.
- `code/controller/current/rc_car_app/runtime.py`: controller loop, AEB gating, arbitration, and motor application.
- `code/controller/current/rc_car_app/vision.py`: all 46 live-selectable checkpoint names through v4.0 and the v3.4 default.
- `code/ai_models_datasets/series_3_and_4/series_4_common.py`: shared PC/CF/PCF architecture and training engine.
- `code/test_files/models/evaluate_sidewalkpilot_models.py`: common-dataset evaluator.
- `docs/steering_model_report.pdf`: 23-page all-series comparison report.
- `docs/steering_eval_current_labels.json`: machine-readable results and historical S1/2 blocks.

Next: preserve a physical AEB result, integrate and replay-test the best v4.1 candidates, and promote a new model only if it improves physical driving over v3.4.
