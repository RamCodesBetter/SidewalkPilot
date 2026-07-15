# Runtime Flow Diagram

This page describes the Raspberry Pi 5 control path in `runtime.py`. The main loop owns controller events and final actuator decisions; camera, Jetson Orin Nano I/O, LiDAR, GPS, dashboard transport, image writes, and optional telemetry use workers or cached latest values so routine I/O does not intentionally block manual control.

## Startup

`code/controller/current/rc_car.py` has no `--model` argument; it calls `run()`. Model selection comes from the dashboard model page, with `RC_CAR_STEERING_MODEL` and the configured default supplying startup state.

`run()` then:

1. Creates runtime state and metrics;
2. Initializes GPIO, PCA9685 steering, motors, and the pygame joystick;
3. Starts available LiDAR, GPS, IMU, camera, Jetson Orin Nano client, CSV, dashboard, and optional InfluxDB components; and
4. Leaves unavailable optional components in their documented fallback state rather than claiming that every sensor is healthy.

## Main loop

The loop is capped by `clock.tick(60)`. Each pass performs these stages:

1. **Controller events:** drain pygame input for steering, throttle/brake, PRND, cruise control, autonomy, AEB, capture, navigation, dashboard controls, signals, and quit.
2. **Capture scheduler:** if run capture is enabled and motion conditions are met, queue the next image/label pair at the configured 10 fps.
3. **LiDAR snapshot:** read the parser's latest scan, compute distances and visualization state, and pass the scan into actuator arbitration. An empty scan does not create an obstacle stop.
4. **Actuator arbitration:** `update_gpio()` computes manual or autonomous commands, applies enabled LiDAR throttle/brake limits, updates yaw correction when its conditions are met, rate-limits motor PWM, and writes steering and motor outputs.
5. **Supporting state:** update takeover clips, optional Influx telemetry, turn signals, dashboard selection, cached temperatures, and Jetson Orin Nano status.
6. **Navigation:** update route state from GPS/odometry and select AUTO or MNUL segment behavior. A mode change affects the following actuator pass.
7. **Dashboard:** enqueue the latest drive, model, camera, LiDAR, navigation, IMU, and system-status payload over the configured USB-network UDP link.
8. **CSV:** write the 46-column telemetry row when `LOG_INTERVAL_SEC` elapses. The configured interval is `0.1 s`, so the nominal rate is 10 Hz; scheduling load can introduce jitter.

## Shutdown

On quit, interruption, or another exit through `finally`, the runtime sets the shutdown event, writes a final CSV row when applicable, finalizes the current photo-run JSON, stops workers, requests linked dashboard shutdown when configured, closes hardware/logging resources, removes only an empty capture folder, and quits pygame.

This is an ordered control loop plus asynchronous workers. It is not a hard-real-time scheduler, and the diagram does not prove fixed worst-case latency.

## Evidence

- `run()` in `code/controller/current/rc_car_app/runtime.py`
- `LOG_INTERVAL_SEC` and controller constants in `code/controller/current/rc_car_app/config.py`
- `AsyncDashboardSender` and the asynchronous Jetson Orin Nano client in the runtime modules

## Related pages

- [System Diagram](system-diagram.md)
- [Safety Arbitration Diagram](safety-arbitration-diagram.md)
- [Runtime Loop](../../runtime-code/runtime-loop.md)
