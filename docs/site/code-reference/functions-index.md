# Functions and Classes Index

Line numbers are omitted because they become stale after normal refactors. Search these symbols in the owning file.

## Runtime

| Symbol | File | Responsibility |
|---|---|---|
| `run` | `rc_car_app/runtime.py` | System initialization, main loop, and shutdown |
| `update_gpio` | `rc_car_app/runtime.py` | Final motor and steering writes |
| `apply_autonomous_controls` | `rc_car_app/runtime.py` | Model command application and safety arbitration |
| `cycle_steering_model` | `rc_car_app/runtime.py` | Dashboard-driven model selection |
| `Hardware` | `rc_car_app/hardware.py` | GPIO/PWM/PCA9685/hall ownership |
| `PCA9685SteeringServo` | `rc_car_app/hardware.py` | Servo pulse output |
| `WebcamVisionProcessor` | `rc_car_app/vision.py` | Camera capture and Raspberry Pi 5 inference interface |
| `JetsonSteeringClient` | `rc_car_app/vision.py` | Background latest-frame Jetson Orin Nano client |
| `resolve_steering_model_path` | `rc_car_app/vision.py` | Early-model local artifact resolution |
| `SteeringInferenceServer` | `rc_car_app/jetson_inference_server.py` | ONNX loading, invocation, and decode |
| `LidarParser` | `rc_car_app/lidar.py` | FHL-LD19 packet parsing |
| `decide_lidar_action` | `rc_car_app/lidar_avoidance.py` | Center-corridor slowdown/hold/emergency decision |
| `NavigationManager` | `rc_car_app/navigation.py` | Route/navigation state |
| `GpsReader` | `rc_car_app/navigation.py` | Background NMEA input |
| `Hub75DashboardSender` | `rc_car_app/hub75_dashboard.py` | Raspberry Pi 5 telemetry transport |
| `DashboardRenderer` | `z2w_dashboard.py` | Zero 2 W HUB75 rendering |

## Training and Evaluation

| Symbol | File | Responsibility |
|---|---|---|
| `SteeringAutonomyV2` | `series_1_and_2/sidewalkpilot_trainer.py` and runtime adapter | Series 1/2 model |
| `SidewalkPilotV3` | `series_3_and_4/series_3_sidewalkpilot_trainer.py` | Series 3 visual/hybrid model |
| `SidewalkPilotV4` | `series_3_and_4/series_4_common.py` | S4 optional-history/multi-horizon model |
| `build_temporal_samples` | `series_3_and_4/series_4_common.py` | Split-safe PC/CF/PCF windows |
| `decode_hybrid` | `series_3_and_4/series_4_common.py` | Class-plus-offset steering decode |
| `temporal_hybrid_loss` | `series_3_and_4/series_4_common.py` | Current/future steering objective |
| `run_fixed_experiment` | `series_3_and_4/series_4_common.py` | Shared Series 4 run implementation and profile selection |
| evaluator entrypoint | `code/test_files/models/evaluate_sidewalkpilot_models.py` | 52-model JSON/PDF generation |

Use `rg '^(def|class) '` in the relevant source directory for a complete generated symbol list.
