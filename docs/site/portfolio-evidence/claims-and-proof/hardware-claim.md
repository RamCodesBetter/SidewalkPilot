# Hardware Claim

SidewalkPilot is a physical Yahboom Ackermann 520M RC platform with a Raspberry Pi
5 controller, Jetson Orin Nano inference host, and Raspberry Pi Zero 2 W dashboard.
The current code contains the interfaces and constants below. Configuration is
evidence of implementation intent; physical photos, bench output, and field logs
are the evidence that a particular assembly worked.

## Current interfaces

- **Steering:** PCA9685 at I2C `0x40`, channel `0`, 50 Hz. Logical steering is
  0/90/180 for left/center/right, with hardware mapping and trim in `hardware.py`.
- **Drive:** AT8236 motor control through four Pi PWM outputs: right forward 19,
  right reverse 20, left forward 25, and left reverse 13.
- **Wheel speed:** hall input on GPIO 24; software uses 455 pulses per revolution
  and a configured 7.0 cm wheel diameter.
- **LiDAR:** FHL-LD19 at 230400 baud through a CP2102 USB serial adapter, normally
  `/dev/ttyUSB0` or a stable by-id path.
- **GPS:** BN880 NMEA input on `/dev/ttyAMA0` at 9600 baud. The board's
  magnetometer has a bench utility but is not fused into the runtime navigation
  controller.
- **Camera:** Raspberry Pi Camera Module 3 Wide through Picamera2, captured at
  1280x720 before model-specific preprocessing.
- **Dashboard:** one Waveshare 64x32 HUB75 panel on a Zero 2 W, receiving UDP over
  the fixed Pi-to-Zero USB network (`192.168.10.1` to `192.168.10.2`, port 8765).
- **IMU:** XIAO MG24 Sense yaw data on `/dev/ttyAMA3` at 115200 for the current
  experimental yaw-control path.

## Boundaries

- The custom Pi breakout PCB is designed but not fabricated.
- Configuration does not prove water resistance, EMI immunity, stopping distance,
  or reliability.
- Series 4 ONNX models are integrated and smoke-tested but have no physical-car
  result yet.

## Evidence

- Code: `config.py`, `hardware.py`, `lidar.py`, `vision.py`, and `yaw_pid.py`.
- Bench utilities: servo, LiDAR, camera, GPS, IMU, controller, and dashboard tools
  under `code/test_files/`.
- Remaining publication work: attach dated wiring photos and selected raw bench
  outputs to the evidence index.

## Related pages

- [System at a Glance](../../start-here/system-at-a-glance.md)
- [Hardware BOM](../../exhibits/tables/hardware-bom-table.md)
- [Evidence Map](../reader-paths/evidence-map.md)
