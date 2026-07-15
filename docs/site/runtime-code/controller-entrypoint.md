# Controller Entrypoint

`code/controller/current/rc_car.py` is intentionally minimal. It imports and calls `rc_car_app.runtime.run()`.

The live entrypoint has no `--model` flag. This was changed so the active version can be selected visibly on the dashboard model page. The default is v3.4, and `RC_CAR_STEERING_MODEL` can override startup selection.

```bash
cd ~/rc_car_code/code/controller/current
car
```

`runtime.run()` initializes state, GPIO/PCA9685, controller input, sensors, camera, background Jetson Orin Nano inference, logging, and dashboard telemetry before entering the main loop.

If no joystick is detected, the controller exits rather than moving without the manual-control interface. Model-load and network failures are handled inside the runtime/inference layers; stale Jetson Orin Nano output is not replayed indefinitely.

See [Model Choices](vision/model-choices.md) and [Runtime Loop](runtime-loop.md).
