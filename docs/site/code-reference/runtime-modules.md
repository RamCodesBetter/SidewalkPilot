# Runtime Modules

The live software is split by ownership boundary so camera/network delays cannot silently become motor-control delays.

| Module | Current role |
|---|---|
| `rc_car.py` | Starts `rc_car_app.runtime.run()`; model selection is handled on the dashboard or by `RC_CAR_STEERING_MODEL` |
| `rc_car_app/runtime.py` | Main loop, controller input, gears, autonomy, safety arbitration, logging, and orderly cleanup |
| `rc_car_app/config.py` | Hardware pins, calibration, thresholds, state defaults, and CSV fields |
| `rc_car_app/hardware.py` | GPIO/PWM/PCA9685/hall ownership and logical-to-physical steering mapping |
| `rc_car_app/vision.py` | Model registry, camera capture, local early-model support, and asynchronous Pi-to-Jon client |
| `rc_car_app/jetson_inference_server.py` | ONNX Runtime provider selection, model hot-swap, Series 1-4 invocation/decoding, and PC/PCF history |
| `rc_car_app/lidar.py` | FHL-LD19 serial parsing and scan freshness |
| `rc_car_app/lidar_avoidance.py` | Center-corridor clear/slow/hold/emergency decisions; no steering |
| `rc_car_app/navigation.py` | GPS parsing, graph loading, A* routing, and route-segment state |
| `rc_car_app/hub75_dashboard.py` | Pi-side dashboard serialization and UDP/serial transport, used behind `AsyncDashboardSender` |
| `rc_car_app/logging_utils.py` | CSV initialization and row writing |
| `z2w_dashboard.py` | Zero 2 W UDP receiver and single HUB75 renderer |

## Runtime Flow

`runtime.run()` initializes state and hardware, connects sensors and the camera, starts background workers, then reads the controller and applies arbitration each tick. Manual stop and LiDAR braking take priority over autonomous motion. Dashboard/logging work must not block actuator updates.

When Jon is configured, the Pi submits only the newest frame. A powered-off or slow Jon cannot make the controller wait synchronously. Returned predictions have a freshness limit; old results are rejected.

## Model Flow

The model registry contains all 46 checkpoints. Early Series 1/2 models can use local PyTorch inference when configured. Series 3/4 run as ONNX on Jon. Series 4 PC/PCF maintain causal history inside the single inference server; CF remains image-only.

## Verification

```bash
python3 -m py_compile code/controller/current/rc_car.py \
  code/controller/current/z2w_dashboard.py \
  code/controller/current/rc_car_app/jetson_inference_server.py
python3 -m compileall code/controller/current/rc_car_app
```

See [Runtime Loop](../runtime-code/runtime-loop.md) and [Jetson Inference Link](../autonomy-stack/camera-steering/jetson-inference-link.md).
