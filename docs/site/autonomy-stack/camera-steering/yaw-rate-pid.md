# Yaw-Rate PID Steering

Optional closed-loop steering that uses a 6-axis IMU (XIAO MG24) yaw-rate signal to correct
the open-loop model or joystick command near center.

## How it works

Without IMU correction, the camera-steering pipeline is open loop: the model outputs a
steering angle and the servo moves without measuring the achieved turn rate. Mechanical
hysteresis (`steering-hysteresis.md`), load, surface,
motor output, and linkage geometry can all contribute to a mismatch between command and motion.

The live runtime wires this path into `update_gpio()`. `ImuReader` reads filtered Z-axis
gyro data from `/dev/ttyAMA3` at 115200 baud. `YawController` has three modes:

- `off`: exact open-loop passthrough;
- `straight` (current default): target zero yaw only when the logical command is within
  5 degrees of center; ordinary turn commands pass through;
- `full`: derive target curvature/yaw for turns as well as straight driving.

The default path uses measured left-approach and right-approach feed-forward values, then
applies a speed-normalized PID correction bounded to 30 degrees. It disengages below
0.05 m/s, in reverse, during a LiDAR override, or when IMU data is not fresh. Live tuning
can adjust Kp, Ki, and Kd in memory from the dashboard TUNE page.

This is shipped code but still experimental control behavior. A field result is valid
evidence only when the run records the selected mode, fresh IMU data, and whether the PID
was engaged.

## Why it matters

Open-loop steering assumes that a commanded angle produces the intended path. Yaw feedback
measures motion rather than relying only on that command. In principle, it can correct
disturbances that a fixed trim cannot represent. The implementation still needs a controlled
before/after field result before claiming improved path tracking.

## Related pages

- `hardware/imu.md`
- `autonomy-stack/camera-steering/servo-output.md`
- `research-and-math/algorithms/pid-cruise-control.md`
