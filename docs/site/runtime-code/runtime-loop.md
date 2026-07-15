# Runtime Loop

The Raspberry Pi 5 controller is a 60 Hz arbitration loop owned by `run()` in `code/controller/current/rc_car_app/runtime.py`. The loop reads already-available state, applies control priority, writes hardware commands, and publishes telemetry. Slow device and network work must not execute synchronously in this loop.

## One Iteration

1. Measure loop time and report any pause of at least `CONTROL_LOOP_STALL_WARN_SEC` (`0.10 s`).
2. Drain Pygame controller events and update stick, trigger, button, D-pad, and page state.
3. Read the latest LiDAR scan snapshot and evaluate the center-corridor policy once.
4. Run `update_gpio()` to arbitrate manual/autonomous throttle, AEB, yaw correction, steering, brake, and gear behavior.
5. Consume cached sensor/navigation state and update dashboard page selection.
6. Queue the newest dashboard payload for its sender worker.
7. Append periodic CSV telemetry.
8. Call `clock.tick(60)` to cap the loop rate.

## Worker Ownership

| Work | Owner | Main-loop behavior |
|---|---|---|
| Raspberry Pi 5 camera capture | `WebcamVisionProcessor` thread | Copy latest BGR frame |
| Photo JPEG writes | Camera save worker | Queue frame or report queue full |
| LiDAR USB-serial parsing | `LidarParser` thread | Read latest scan |
| GPS UART parsing | `GpsReader` thread | Read latest fix |
| IMU serial parsing | `ImuReader` thread | Read latest yaw rate |
| Jetson Orin Nano TCP/JPEG/inference | `AsyncJetsonSteeringClient` thread | Submit latest frame and read fresh cached result |
| Dashboard UDP/JSON | `AsyncDashboardSender` thread | Replace pending payload with newest state |
| Influx telemetry | `InfluxLogger` worker | Queue measurement |
| Interruption clip encoding | Recorder worker | Queue captured JPEGs |

Both Jetson Orin Nano and dashboard workers are **latest-value** boundaries. If consumption is slower than capture, old pending work is replaced instead of building an increasingly stale queue.

## Offline Jetson Orin Nano Behavior

Jetson Orin Nano uses `10.42.0.2:8770`. A failed TCP connect can consume the complete `0.4 s` socket timeout, but that wait occurs only in `AsyncJetsonSteeringClient`. Manual steering and dashboard updates continue while Jetson Orin Nano is powered off. Autonomous mode receives no fresh model result and hard-stops rather than reusing an old command.

`JETSON_RESULT_MAX_AGE_SEC` is `0.25 s`. A result older than that is unavailable for control even if it remains in the cache.

## Timing Diagnostics

The runtime emits:

```text
[loop-stall] control loop paused 412ms (auto=0)
```

for pauses at or above 100 ms, rate-limited to one message per second. A repeating message with Jetson Orin Nano off indicates a regression: network I/O has reached the control thread again. Camera, LiDAR, dashboard, and servo updates pausing together is also evidence of a main-loop stall rather than Bluetooth latency.

## Bench Check

1. Keep the wheels clear of the ground.
2. Power the Raspberry Pi 5 and Zero 2 W, but leave Jetson Orin Nano off.
3. Start the controller service and move the steering stick continuously.
4. Change dashboard pages while watching the camera/LiDAR pages.
5. Confirm servo and display motion stay smooth and `journalctl` has no repeating loop-stall pattern.

```bash
sudo systemctl restart sidewalkpilot-rpi-car.service
journalctl -u sidewalkpilot-rpi-car.service -f
```

Regression coverage:

```bash
python3 code/test_files/controller/test_async_jetson_client.py
python3 code/test_files/lidar/test_lidar_center_aeb.py
```

See [Model Inference](../autonomy-stack/camera-steering/model-inference.md) and [Dashboard Sender](dashboard/sender.md).
