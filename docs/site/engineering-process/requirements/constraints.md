# Constraints

These are the verified constraints that shape the current design.

## Hardware

- The Camera Module 3 Wide is integrated through Picamera2 on the Raspberry Pi 5. The 81,237-frame Series 3/4 dataset was captured through this camera path.
- Steering uses a PCA9685 at I2C `0x40`, channel `0`, 50 Hz. Logical labels remain `0..180`; physical steering compensation stays in `hardware.py`.
- The LD19 LiDAR currently uses a CP2102 USB-serial adapter at 230400 baud, normally `/dev/ttyUSB0`. `/dev/ttyAMA2` is a former transport, not the current command path.
- GPS data uses `/dev/ttyAMA0` at 9600 baud.
- The XIAO MG24 IMU feeds the optional yaw-rate controller; IMU correction is bypassed when its mode is off, data is stale, the car is not moving, or reverse is selected.

## Compute and Connectivity

- The Raspberry Pi 5 owns final motor, steering, and safety decisions.
- Jetson Orin Nano performs Series 3/4 ONNX inference over direct Ethernet at `10.42.0.2:8770`.
- Camera/Jetson Orin Nano work is asynchronous so it does not block local controller polling.
- Dashboard telemetry is UDP over the dedicated Raspberry Pi 5–Zero 2 W USB network. There is no Wi-Fi fallback in the current configuration.
- Each computer must be restarted or have its owning service restarted after synced code changes.

## Safety

- Manual takeover remains available from the Xbox controller.
- LiDAR does not steer. When AEB is enabled, it can cap forward throttle and request a hard brake from center-corridor clearance.
- A stale or unavailable Jetson Orin Nano result is not a valid autonomous command.
- Configured distance thresholds are policy values, not proof of stopping distance. Physical tests under the real payload are still required.

## Data and Claims

- Stored steering labels are logical degrees; stored throttle labels use the absolute physical `0.0..1.0` PWM fraction (`0.55` means 55%).
- The 81,237-frame Series 3/4 release is real driving data. CARLA is published separately; claims about whether a specific historical checkpoint used CARLA require that run's recorded roots or logs.
- Offline metrics rank candidates. Only field testing promotes a live baseline.
- Series 4.0 is runtime-supported and field-tested. Series 4.1 is trained, exported, and offline-evaluated but not yet integrated or field-tested.
