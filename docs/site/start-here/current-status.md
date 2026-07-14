# Current Status

Last updated: **July 13, 2026**.

## Working Baseline

- **Steering model:** Series 3.4, running as ONNX on the Jetson Orin Nano.
- **Field result:** v3.4 completed every shadow case presented in the latest comparison and ranked above v3.4b, v3.3, and v3.3b.
- **Steering calibration:** `+12D` center trim, a normalized PCA9685 center offset of `0.133333` and physical center command of 102 degrees.
- **LiDAR connection:** UART on the Pi; scan processing runs independently from Jetson inference.
- **LiDAR control:** one center safety corridor only. It may reduce throttle or hard-stop, but never steer.
- **AEB toggle:** gates all LiDAR throttle and brake intervention in both manual and autonomous driving. Telemetry remains visible while disabled.
- **Series 4:** planning scaffold only. No v4 model is trained, deployed, or selectable.

## Immediate Validation Needed

The center-only AEB policy is code-tested but still requires a physical bench/field test:

1. With AEB OFF, place an obstacle in the center corridor and verify no slowdown, stop, or steering override occurs.
2. With AEB ON, verify a side obstacle causes no control change.
3. Move a center obstacle inward and verify physical throttle falls from 100% to 55%.
4. Verify the car holds the 55% minimum-moving command before the emergency rung.
5. Cross the 1.05 m emergency boundary and verify a hard brake.
6. Repeat in autonomous mode and confirm the model remains the only steering source.

Do not treat an enabled AEB indicator as proof that LiDAR data is fresh. An empty/disconnected scan produces no obstacle intervention; sensor health must be checked separately.

## Key Files

- `code/controller/current/rc_car_app/lidar_avoidance.py`: center distance, governor, and emergency decision.
- `code/controller/current/rc_car_app/runtime.py`: AEB gating and motor application.
- `code/controller/current/z2w_dashboard.py`: center-corridor scan page.
- `code/controller/current/rc_car_app/vision.py`: v3.4 default and selectable models.
- `code/ai_models_datasets/series_4/SERIES4_PLAN.md`: Series 4 promotion contract.
- `docs/steering_model_report.pdf`: current offline model report.

Next: run the physical center-corridor AEB procedure, save the result, then define the first single-variable Series 4 architecture experiment.
