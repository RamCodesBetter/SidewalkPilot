# System at a Glance

## Three-Computer Design

- **Raspberry Pi 5:** The central controller. It runs `rc_car.py` and
  `rc_car_app`; manual control and local safety remain authoritative.
- **Jetson Orin Nano:** The inference computer on an offline Ethernet link
  through the Pi. It runs `jetson_inference_server.py`. The Pi discards missing
  or stale predictions and keeps its control loop running.
- **Raspberry Pi Zero 2 W:** The dashboard computer on the dedicated USB
  network at `192.168.10.2`. It runs `z2w_dashboard.py`. The dashboard shows
  `NO LINK` when telemetry stops, while motion control continues independently.

## Hardware Map

- **Forward vision:** Pi Camera Module 3 Wide, connected to the Pi 5 through
  libcamera/Picamera2.
- **Obstacle distance:** FHL-LD19 LiDAR, connected to the Pi 5 through CP2102
  USB serial. It normally appears as `/dev/ttyUSB0` or a stable by-id path.
- **Position:** BN880 GPS, connected to the Pi 5 through UART.
- **Compass Heading (Bench Only):** HMC5883L-compatible compass, connected to
  the Pi 5 through I2C. Live navigation does not consume its heading.
- **Wheel speed:** Hall-effect sensor, connected to the Pi 5 through GPIO.
- **Steering:** High-torque servo through the PCA9685, controlled by the Pi 5
  over I2C PWM.
- **Drive motors:** AT8236 motor controller, controlled by the Pi 5 through
  GPIO PWM and direction lines.
- **Human control:** Xbox Series X controller, connected to the Pi 5 through
  Bluetooth HID.
- **Telemetry:** Waveshare 64x32 HUB75 panel, driven by the Zero 2 W through
  its GPIO matrix driver.

## Decision Priority

The system does not average every input together. Higher-priority controls override lower-priority ones:

1. Quit, cleanup, and explicit shutdown.
2. Manual brake and safety stop conditions.
3. LiDAR hard brake when AEB is enabled.
4. LiDAR throttle governor when AEB is enabled.
5. Manual or autonomous steering/throttle command.
6. Dashboard and logging, which are isolated or rate-limited so routine work does not intentionally hold up motion control.

## Model Interfaces

The camera frame is normalized OpenCV BGR data. The active decoder is selected from the ONNX signature:

```text
Series 3.1+: 9 steering-class logits + 9 class-local offsets + 1 throttle
Series 4 PC:  1 x (9 logits + 9 offsets), plus three-target history input
Series 4 CF:  4 x (9 logits + 9 offsets), image input only
Series 4 PCF: 4 x (9 logits + 9 offsets), plus three-target history input
```

Only horizon zero commands live steering. PC/PCF history is initialized to `[90,90,90]`, updated after each inference, and reset on model changes, reconnects, and manual/status periods. Series 4 does not predict throttle. LiDAR and runtime policy constrain motion separately.

## Current Calibration and Limits

- Steering center trim: `+12D`.
- Normalized center offset: `0.133333`.
- Physical servo center command: approximately 102 degrees.
- Camera and inference cadence target: approximately 30 frames/inferences per second; the runtime reports measured camera FPS and Jetson IPS separately, and neither is guaranteed by the target value.
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

Check the direct Ethernet link from the Raspberry Pi:

```bash
ping -c 3 10.42.0.2
```

On Jon:

```bash
ip -br addr
ss -ltnp | grep 8770
pgrep -af jetson_inference_server.py
nvidia-smi
```

On the Zero 2 W:

```bash
sudo systemctl status sidewalkpilot-z2w-dashboard.service -l --no-pager
journalctl -u sidewalkpilot-z2w-dashboard.service -n 100 -l --no-pager
```

For the complete runtime sequence, continue to [Data Flow](../autonomy-stack/architecture/data-flow.md).
