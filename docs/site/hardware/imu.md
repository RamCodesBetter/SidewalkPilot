# IMU (Yaw Rate)

The 6-axis XIAO MG24 IMU provides yaw-rate feedback for closed-loop steering experiments.

The IMU is a Seeed XIAO MG24 with a 6-axis sensor (3-axis accelerometer + 3-axis
gyroscope). It was added to give the steering loop a direct measurement of how fast
the car is actually rotating (yaw rate), rather than inferring turn from the servo
command alone. It is wired to the Raspberry Pi 5 UART on `/dev/ttyAMA3` (GPIO 8/9).

**Status: implemented and experimental.** Firmware, verifier, and calibration utilities
exist in `code/test_files`. The live runtime starts `ImuReader` and `YawController` when
`STEERING_YAW_PID_MODE` is not `off`; the checked-in default is `straight`. In that mode,
the controller corrects yaw near logical center and passes real turn commands through.
If the IMU cannot start or its data is stale, the steering path falls back to open loop.
This implementation status is not a blanket field-validation claim: a run should show the
startup `Yaw-rate PID steering ENABLED` line and fresh yaw telemetry before its result is
attributed to the controller.

## How It Works

- The MG24 streams inertial data over UART to the Raspberry Pi 5. The gyro's yaw axis gives the car's
  turn rate directly.
- In default `straight` mode, commands within 5 degrees of logical center target zero yaw;
  the PID trims around direction-dependent feed-forward values. `full` mode can also track
  turn-rate targets, but it is not the checked-in default.
- The controller supports `off` for exact open-loop passthrough, `straight` for center-only
  correction, and `full` for experimental turn-rate targets. PID correction is bounded to
  30 degrees and disengages below 0.05 m/s, in reverse, during LiDAR intervention, or when
  IMU data is stale.
- Kp, Ki, and Kd can be adjusted in memory from the dashboard tuning page. A field record
  must preserve those values rather than assuming the checked-in defaults were active.
- Bench calibration utilities are tracked in `code/test_files`. A local run may produce files such as `code/test_files/sensors/imu_calib.csv`, but that output is not a tracked publication file in this branch.

## Why It Matters

- Bench work observed direction-dependent return behavior: the same nominal center command
  did not always produce the same motion after a left versus right approach. The checked-in
  controller therefore uses different feed-forward centers (`119.5` and `107.8`). The branch
  does not contain a traceable measurement supporting a single exact hysteresis angle, so none
  is claimed here.
- The current design combines measured feed-forward values with inertial feedback instead
  of relying only on a guessed center offset.

## Related Pages

- [Steering Servo](steering-servo.md)
- [Pin Map](wiring/pin-map.md)
