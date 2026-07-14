# Current Status

Last updated: **July 14, 2026**.

## Working Baseline

- **Steering model:** Series 3.4, running as ONNX on the Jetson Orin Nano.
- **Field result:** v3.4 completed every shadow case presented in the July 13 comparison and ranked above v3.4b, v3.3, and v3.3b.
- **Steering calibration:** `+12D` center trim, normalized PCA9685 center offset `0.133333`, and physical center command near 102 degrees.
- **LiDAR connection:** FHL-LD19 through CP2102 USB serial at `/dev/ttyUSB0`; scan processing is independent from Jetson inference.
- **LiDAR control:** one center safety corridor. It can reduce throttle or hard-brake, but it never steers.
- **AEB toggle:** gates every LiDAR throttle/brake intervention in manual and autonomous modes. Telemetry remains visible while intervention is disabled.
- **Dashboard:** Zero 2 W plus one Waveshare 64x32 HUB75 panel over a dedicated USB network. No production MAX7219 display and no Wi-Fi telemetry fallback.
- **Control responsiveness:** verified on the physical car with the Jetson powered off after network, file-scan, and temperature work was removed from the manual-control path.
- **Series 4:** planning only. No v4 model is trained, deployed, or selectable.

## LiDAR Motion Policy

| Center distance | Action |
|---|---|
| At least 1.65 m | No LiDAR throttle limit |
| 1.65 m to 1.25 m | Reduce reference throttle linearly from 100% to 60% |
| 1.25 m to 1.05 m | Hold 60% reference throttle |
| At or below 1.05 m | Hard brake |

The 60% value is in the reference moving range. It corresponds to 82% on the physical 0-to-100 command/label range because physical commands below 55% do not move this car.

## Immediate Validation Needed

The center-only AEB policy is code-tested but still requires a recorded physical test:

1. With AEB OFF, place an obstacle in the center corridor and verify no slowdown, stop, or steering override.
2. With AEB ON, verify a side obstacle causes no control change.
3. Move a center obstacle inward and verify reference throttle falls from 100% to 60%.
4. Verify the car holds the 60% reference command before the emergency rung.
5. Cross the 1.05 m emergency boundary and verify a hard brake.
6. Repeat in autonomous mode and confirm the model remains the only autonomous steering source.

Do not treat an enabled AEB indicator as proof that LiDAR data is fresh. An empty, stale, or disconnected scan may produce no obstacle intervention; sensor health must be checked separately.

## Evidence Gaps

- The July 13 model comparison lacks a formal route identifier, weather record, takeover count, and linked video clips.
- Current LiDAR behavior has automated tests but needs a saved physical pass/fail record after the latest policy change.
- Series 4 is a hypothesis, not a result.
- The current system has no claim of unattended operation or unrestricted pedestrian handling.

## Key Files

- `code/controller/current/rc_car_app/lidar_avoidance.py`: center distance, throttle governor, and emergency decision.
- `code/controller/current/rc_car_app/runtime.py`: controller loop, AEB gating, arbitration, and motor application.
- `code/controller/current/rc_car_app/vision.py`: selectable models and inference contracts.
- `code/controller/current/z2w_dashboard.py`: dashboard receiver and center-corridor LiDAR view.
- `code/ai_models_datasets/series_4/SERIES4_PLAN.md`: planning scaffold only.
- `docs/steering_model_report.pdf`: current offline comparison report.

Next: record the physical center-corridor AEB test, then define the first causal Series 4 baseline.
