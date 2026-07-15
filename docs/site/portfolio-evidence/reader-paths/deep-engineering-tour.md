# Deep Engineering Tour

This tour connects the project story to the source files, model contracts, data, evaluation, and failure-handling decisions a technical reviewer can inspect.

## 1. Three Computers, One Authority

The Jetson Orin Nano is an inference service. The Raspberry Pi 5 sends the newest JPEG and selected model version over dedicated Ethernet. Jetson Orin Nano loads the matching ONNX, returns decoded steering/probabilities, and never directly controls an actuator.

The Raspberry Pi 5 is the final control authority. It reads the Xbox controller, captures camera frames, reads LiDAR/GPS/IMU/hall telemetry, applies safety policy, drives the PCA9685 steering servo and motor controller, and records logs.

The Zero 2 W is a display service. It receives UDP telemetry over a dedicated USB network and renders the Waveshare 64x32 HUB75 panel. Dashboard failure does not control motion.

| Responsibility | Source |
|---|---|
| Entrypoint | `code/controller/current/rc_car.py` |
| Main loop and arbitration | `code/controller/current/rc_car_app/runtime.py` |
| Hardware ownership | `code/controller/current/rc_car_app/hardware.py` |
| Model registry and Raspberry Pi 5 inference client | `code/controller/current/rc_car_app/vision.py` |
| Jetson Orin Nano ONNX server | `code/controller/current/rc_car_app/jetson_inference_server.py` |
| LiDAR parser | `code/controller/current/rc_car_app/lidar.py` |
| LiDAR policy | `code/controller/current/rc_car_app/lidar_avoidance.py` |
| Dashboard sender | `code/controller/current/rc_car_app/hub75_dashboard.py` |
| Dashboard receiver | `code/controller/current/z2w_dashboard.py` |

## 2. Keeping Manual Control Responsive

An earlier runtime failure looked like Bluetooth lag: steering and dashboard updates ran smoothly, paused, then resumed. `jstest` changed instantly, including while Jetson Orin Nano was off, so the controller link was not the bottleneck.

The audit found recurring work on the control path, especially network waits to an unavailable Jetson Orin Nano, repeated photo-directory scans, and temperature subprocesses. Camera-to-Jetson Orin Nano communication now uses a background worker with latest-frame semantics. Dashboard networking is asynchronous, and recurring file/subprocess work is cached or moved away from each controller tick.

The field retest with Jetson Orin Nano powered off removed the observed pauses. That is a bounded result from one hardware retest, not a general hard-real-time guarantee.

## 3. Model Evolution

### Series 1 and 2

`SteeringAutonomyV2` accepts a `3x66x200` normalized image and directly regresses steering. It contains 672,877 trainable parameters. Series 1 established the end-to-end loop; Series 2 refined data and tested fixed HSV/CLAHE preprocessing.

### Series 3

Series 3 increases input to `3x180x320` and uses a six-stage visual backbone. v3.0 has a two-output regression contract. v3.1 through v3.4b use a 19-value hybrid head:

```text
9 steering-class logits + 9 within-class offsets + 1 throttle
```

The selected class chooses one of `HL, L, L+, SL, ST, SR, R, R+, HR`. A sigmoid-bounded local offset recovers a continuous steering value inside that class. v3.4 has 5,534,115 parameters and the current FP32 ONNX artifact is 22,136,200 bytes.

### Series 4

Series 4 keeps the Series 3 visual backbone, removes throttle learning, and compares three temporal contracts:

| Contract | Runtime inputs | Output |
|---|---|---|
| PC (`4.0p/r`) | image plus three prior steering targets | `[batch,1,18]` |
| CF (`4.0f/g`) | image only | `[batch,4,18]` |
| PCF (`4.0a/c`) | image plus three prior steering targets | `[batch,4,18]` |

Each 18-value horizon contains nine logits and nine local offsets. Only horizon zero commands steering. Future horizons are training supervision, not future inputs. The runtime initializes PC/PCF history to `[90,90,90]`, appends one decoded result per inference, and resets history on model changes, reconnects, and manual/status periods.

## 4. Training Controls

Series 3 and 4 share the same 81,237-image real-world dataset and split procedure. Series 4 therefore changes the learning contract, not the base data membership. The trainer sorts paths into contiguous 100-sample split windows. Series 4 temporal samples are then rejected if they cross a train/validation boundary, a detected capture-run boundary, or a timestamp gap greater than 0.25 seconds.

The completed Series 4 experiments used the RTX 6000 Ada GPU, weighted sampling, lighting/color transforms, horizontal balancing, and synthetic shadow bands. Each of those three recorded runs produced a final artifact and a best-current-target-validation artifact, exported ONNX, and logged its comparison metrics to W&B.

The three Series 4 runs each used 25 epochs and produced six artifacts. All six passed ONNX signature and CUDA inference checks. They are not field-selected.

## 5. Why MAE Is Not Enough

The steering distribution contains many straight frames. A model can lower average error by staying close to 90 degrees while failing real turns. The evaluator therefore reports:

- Bal9: macro recall across nine steering classes;
- Turn exact and turn within one adjacent class;
- Straight exact recall;
- Mean and median absolute steering error;
- Signed error for left/right bias;
- Confusion matrices and hold-last baselines.

All 46 checkpoints are scored on the same frozen 6,952-frame Series 3/4 challenge subset after architecture-specific preprocessing and decoding. Offline evaluation orders candidates; a physical-car comparison promotes them.

## 6. Current Model Evidence

v3.4 is the field-selected baseline. During the July 13 comparison it handled every shadow case presented and the tested ordinary left/right turns. v3.4b was slightly worse; v3.3 and v3.3b regressed relative to their earlier references.

That verdict is qualitative because route, weather, clip identifiers, and takeover count were not preserved. The next field test uses a stricter record and compares v3.4 against the Series 4 candidates in a fixed order.

## 7. LiDAR Safety Boundary

The FHL-LD19 is connected through CP2102 USB serial. The current policy evaluates a center corridor only. At or above 1.65 m clearance the governor allows full reference throttle; it ramps toward 60% reference throttle by 1.25 m and commands the hard-stop backstop at 1.05 m.

LiDAR does not choose left or right. Earlier lane-based swerve logic was removed because obstacle points do not prove where the sidewalk boundary is. A deterministic swerve could avoid one object while driving into grass, a curb, or another hazard.

When AEB is disabled for a controlled test, its slowdown and hard-brake interventions are disabled in both manual and autonomous modes. The human operator remains responsible for stopping the vehicle.

## 8. Steering Calibration

Training labels preserve a clean absolute 0-to-180 convention. Hardware mapping separately handles mechanical limits and center calibration. The current configured center trim is `+12D`; that value is a software/hardware setting, not a learned label change.

This separation matters for reproducibility: a photo labeled 90 remains “center target” even if the physical linkage later needs a different PCA9685 command to achieve it.

## 9. Observability and Reproducibility

The dashboard exposes model choice, steering, camera state, navigation, temperature, and LiDAR state. Drive CSVs preserve control and sensor values. W&B preserves training curves. Hugging Face stores public model/dataset artifacts, while GitHub stores code and documentation.

The generated PDF and JSON report are committed at:

- `docs/steering_model_report.pdf`
- `docs/steering_eval_current_labels.json`

For each future field claim, the evidence standard adds model hash, route segment, conditions, AEB state, duration/distance, takeover count/reasons, and linked clips/logs.

## 10. What Remains Open

- Field-test the six Series 4 artifacts against v3.4.
- Preserve a repeatable physical test for the current LiDAR slowdown/stop policy.
- Collect long-duration controller-loop latency traces rather than relying only on observed smoothness.
- Continue collecting difficult turn-in-shadow cases when field failures identify a real gap.
- Keep unattended/public-road operation outside the project scope.

Continue with the [Evidence Map](evidence-map.md), [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md), and [Safety Overview](../../safety-case/safety-overview.md).
