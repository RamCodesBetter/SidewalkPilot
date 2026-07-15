# Build Overview

SidewalkPilot is built on a Yahboom Ackermann 520M chassis and carries three computers, a camera, LiDAR, GPS/compass, wheel-speed sensing, steering and motor electronics, a dashboard, and several separate power sources. It is closer to a mobile systems-integration bench than a stock RC car.

## Major Assemblies

| Assembly | Main parts | Purpose |
|---|---|---|
| Chassis and steering | Yahboom Ackermann 520M, high-torque steering servo, steering rods/linkage | Physical vehicle and car-like front-wheel geometry |
| AI compute | Jetson Orin Nano | ONNX camera-steering inference |
| Main controller | Raspberry Pi 5, PCA9685, AT8236 interface wiring | Sensors, controller, servo, motors, safety, logs |
| Display computer | Zero 2 W, Waveshare 64x32 HUB75 panel | Independent live telemetry display |
| Vision | Raspberry Pi Camera Module 3 Wide | Forward sidewalk image stream and training photos |
| Obstacle sensing | Youyeetoo FHL-LD19 360-degree LiDAR, CP2102 USB adapter | Center-corridor slowdown and emergency braking |
| Navigation | BN880 GPS and HMC5883L-compatible compass | GPS fixes feed the route manager; compass is currently bench-only |
| Motion sensing | Hall-effect sensor | Wheel speed estimate |
| Manual control | Xbox Series X controller | Steering, throttle, brake, model/page controls, takeover, quit |

## Compute and Network Layout

The Raspberry Pi 5 is the hub.

- **Raspberry Pi 5 to Jetson Orin Nano:** dedicated Ethernet, Raspberry Pi 5 `10.42.0.1`, Jetson Orin Nano `10.42.0.2`, inference TCP port `8770`.
- **Raspberry Pi 5 to Zero 2 W:** USB Ethernet gadget, Raspberry Pi 5 `192.168.10.1`, Zero 2 W `192.168.10.2`, telemetry UDP port `8765`.
- **Xbox controller:** Bluetooth HID directly to the Raspberry Pi 5.
- **LiDAR:** USB 3.0 through CP2102, current serial device `/dev/ttyUSB0`.

The two wired links are separate. Dashboard recovery must not rewrite the Jetson Orin Nano Ethernet configuration, and Jetson Orin Nano availability must not determine whether the dashboard works.

## Power Domains

The project uses separate sources because compute, motors, and the display have different load behavior:

- INIU 140 W power bank for Jetson Orin Nano compute;
- INIU 45 W power bank for Raspberry Pi/auxiliary compute;
- OVONIC 3S LiPo for drive motors;
- OVONIC 2S LiPo for the display domain;
- Buck conversion and fusing where the load requires regulated voltage.

Exact wiring, converter ratings, connector polarity, and fuse selection must be checked against the physical build before reproduction. Software documentation is not a substitute for measuring the assembled power rails. Never connect an unverified LiPo or buck output directly to a Raspberry Pi 5, Jetson Orin Nano, servo, or display.

## Control Wiring

Current software assignments include:

| Function | Assignment |
|---|---|
| PCA9685 | I2C address `0x40`, channel 0, 50 Hz |
| Steering pulse range | 1000 to 2000 microseconds |
| Right motor forward/backward | GPIO 19 / GPIO 20 |
| Left motor forward/backward | GPIO 25 / GPIO 13 |
| Hall sensor | GPIO 24 |
| LiDAR | CP2102 USB serial; no current GPIO motor-enable line |

The live runtime source of truth is `code/controller/current/rc_car_app/config.py`. Pin changes must update the wiring document, bench test, and config together.

## Steering Reality

The steering mechanism is not treated as a perfect mathematical servo. Vehicle load, linkage geometry, backlash, and direction of approach affect the wheel angle. The project has used:

- Fixed-angle PCA9685 tests;
- Controller-driven 15-degree step tests;
- Live center-trim adjustment;
- Left/right wheel regression plots;
- Direction-dependent feed-forward calibration;
- IMU yaw-rate experiments.

The current center trim is `+12D`. Reference steering limits are intentionally narrower than absolute hardware commands during normal driving. Tight absolute commands remain a separate future maneuver decision, not a default training range.

## Bring-Up Order

1. Raise the car so wheels cannot drive it unexpectedly.
2. Inspect power polarity, fuse state, loose connectors, and steering linkage.
3. Power the Zero 2 W/display and verify the dashboard receiver service.
4. Power the Raspberry Pi 5 and verify controller, camera, LiDAR, and USB dashboard link.
5. Power the Jetson Orin Nano and verify `10.42.0.2:8770` only when autonomous inference is needed.
6. Confirm manual steering, brake, and quit before placing the car on the ground.
7. Run low-speed sensor and AEB checks before autonomy.

The software is designed to tolerate the Jetson Orin Nano being absent without manual-control lag. That is a failure-mode property, not permission to skip the manual bench check.

## Useful Bench Commands

```bash
python code/test_files/steering/pca9685_servo_test.py
python code/test_files/sensors/hall_sensor_test.py
python code/test_files/lidar/lidar_viewer.py
python code/test_files/sensors/bn880_test.py
python code/test_files/controller/xbox_test.py
sudo python code/test_files/display/hub75_rgbmatrix_test.py
```

Run only one program that owns a device at a time. Stop the live car service before opening the same camera, serial port, PCA9685 channel, or GPIO from a test tool.

## Recurring Physical Failure Modes

| Symptom | Likely area |
|---|---|
| USB `error -110` or failure to enumerate | Cable, connector, damaged port, power/ground, host timing |
| Steering returns differently from left and right | Linkage hysteresis, servo load, calibration, rod geometry |
| Car pulls more as throttle rises | Left/right motor-force imbalance, not only steering trim |
| Dashboard shows `NO LINK` | Controller not sending, dashboard service stopped, or USB network unavailable |
| LiDAR shows no points | Serial ownership, CP2102/device path, LiDAR power, packet stream |
| Controls pause rhythmically | Blocking work inside the runtime loop or repeated network timeouts |

Continue with [System at a Glance](../start-here/system-at-a-glance.md) for software ownership and [Safety Overview](../safety-case/safety-overview.md) before field operation.
