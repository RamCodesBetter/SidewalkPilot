# Runtime Modules

The live software is split by ownership boundary so camera/network delays cannot silently become motor-control delays.

| Module | Current role |
|---|---|
| `rc_car.py` | Starts `rc_car_app.runtime.run()`; model selection is handled on the dashboard or by `RC_CAR_STEERING_MODEL` |
| `rc_car_app/runtime.py` | Main loop, controller input, gears, autonomy, safety arbitration, logging, and orderly cleanup |
| `rc_car_app/config.py` | Hardware pins, calibration, thresholds, state defaults, and CSV fields |
| `rc_car_app/hardware.py` | GPIO/PWM/PCA9685/hall ownership and logical-to-physical steering mapping |
| `rc_car_app/vision.py` | Model registry, camera capture, local early-model support, and asynchronous Raspberry Pi 5–Jetson Orin Nano client |
| `rc_car_app/jetson_inference_server.py` | ONNX Runtime provider selection, model hot-swap, Series 1-4 invocation/decoding, and supplied PC/PCF-history validation |
| `rc_car_app/lidar.py` | FHL-LD19 serial parsing and scan freshness |
| `rc_car_app/lidar_avoidance.py` | Center-corridor clear/slow/hold/emergency decisions; no steering |
| `rc_car_app/navigation.py` | GPS parsing, graph loading, A* routing, and route-segment state |
| `rc_car_app/hub75_dashboard.py` | Raspberry Pi 5 dashboard serialization and UDP/serial transport, used behind `AsyncDashboardSender` |
| `rc_car_app/logging_utils.py` | CSV initialization and row writing |
| `z2w_dashboard.py` | Zero 2 W UDP receiver and single HUB75 renderer |

## Runtime Flow

`runtime.run()` initializes state and hardware, connects sensors and the camera, starts background workers, then reads the controller and applies arbitration each tick. Manual stop and LiDAR braking take priority over autonomous motion. Dashboard/logging work must not block motor or steering updates.

When Jetson Orin Nano is configured, the Raspberry Pi 5 submits only the newest frame. A powered-off or slow Jetson Orin Nano cannot make the controller wait synchronously. Returned predictions have a freshness limit; old results are rejected.

## Model Flow

The live registry contains 46 checkpoints through Series 4.0. Early Series 1/2 models can use local PyTorch inference when configured. Series 3/4.0 run as ONNX on Jetson Orin Nano. The Raspberry Pi 5 client maintains and sends causal history for Series 4.0 PC/PCF; CF remains image-only. The six Series 4.1 models are present in the offline report but are not yet registered for live use.

## Verification

```bash
python3 -m py_compile code/controller/current/rc_car.py \
  code/controller/current/z2w_dashboard.py \
  code/controller/current/rc_car_app/jetson_inference_server.py
python3 -m compileall code/controller/current/rc_car_app
```

See [Runtime Loop](../runtime-code/runtime-loop.md) and [Jetson Orin Nano Inference Link](../autonomy-stack/camera-steering/jetson-inference-link.md).
