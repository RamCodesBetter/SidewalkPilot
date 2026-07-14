# System At A Glance

## Three-Computer Design

| System | Address or link | Runs | Failure behavior |
|---|---|---|---|
| Raspberry Pi 5 | Central controller | `rc_car.py` and `rc_car_app` | Manual control and local safety remain authoritative |
| Jetson Orin Nano | Offline Ethernet link through the Pi | `jon_server.py` | Missing or stale predictions are discarded; controller loop continues |
| Raspberry Pi Zero 2 W | Dedicated USB network, `192.168.10.2` | `z2w_dashboard.py` | Dashboard shows `NO LINK`; motion control continues independently |

## Sensor And Actuator Map

| Function | Device | Read or controlled by | Production interface |
|---|---|---|---|
| Forward vision | Pi Camera Module 3 Wide | Raspberry Pi 5 | libcamera/Picamera2 |
| Obstacle distance | FHL-LD19 LiDAR | Raspberry Pi 5 | CP2102 USB serial, `/dev/ttyUSB0` |
| Position | BN880 GPS | Raspberry Pi 5 | UART |
| Heading | HMC5883L compass | Raspberry Pi 5 | I2C |
| Wheel speed | Hall-effect sensor | Raspberry Pi 5 | GPIO |
| Steering | High-torque servo through PCA9685 | Raspberry Pi 5 | I2C PWM |
| Drive motors | AT8236 motor controller | Raspberry Pi 5 | GPIO PWM/direction |
| Human control | Xbox Series X controller | Raspberry Pi 5 | Bluetooth HID |
| Telemetry | Waveshare 64x32 HUB75 panel | Zero 2 W | Zero 2 W GPIO matrix driver |

## Decision Priority

The system does not average every input together. Higher-priority controls override lower-priority ones:

1. Quit, cleanup, and explicit shutdown.
2. Manual brake and safety stop conditions.
3. LiDAR hard brake when AEB is enabled.
4. LiDAR throttle governor when AEB is enabled.
5. Manual or autonomous steering/throttle command.
6. Dashboard and logging, which must never hold up motion control.

## Model Interface

The camera frame is normalized BGR data. The Series 3.1+ model returns 19 values:

```text
9 steering-class logits + 9 class-local offsets + 1 throttle output
```

The current runtime uses steering from the model but does not learn operational throttle from the Series 3 dataset because the collected throttle distribution is not sufficiently informative. LiDAR and runtime policy constrain motion separately.

## Current Calibration And Limits

- Steering center trim: `+12D`.
- Normalized center offset: `0.133333`.
- Physical servo center command: approximately 102 degrees.
- Camera and target inference cadence: approximately 30 frames/inferences per second.
- Main control-loop target: 60 Hz.
- Jetson steering freshness limit: 0.25 seconds.
- LiDAR center corridor only; no obstacle-avoidance steering.
- AEB slowdown begins at 1.65 m and hard braking begins at 1.05 m.

These are software settings and measured operating choices, not a safety certification. See [Current Status](current-status.md) and [Operating Limits](../safety-case/safety-overview.md).

## Fast Verification

On the Raspberry Pi:

```bash
sudo systemctl status sidewalkpilot-rpi-car.service -l --no-pager
journalctl -u sidewalkpilot-rpi-car.service -n 100 -l --no-pager
```

On the Zero 2 W:

```bash
sudo systemctl status sidewalkpilot-z2w-dashboard.service -l --no-pager
journalctl -u sidewalkpilot-z2w-dashboard.service -n 100 -l --no-pager
```

For the complete runtime sequence, continue to [Data Flow](../autonomy-stack/architecture/data-flow.md).
