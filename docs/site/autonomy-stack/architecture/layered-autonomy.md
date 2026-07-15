# Layered Autonomy

The Raspberry Pi combines operator state, model output, LiDAR policy, and hardware limits before writing actuators.

## Current Order

1. Poll Xbox events and runtime state.
2. Read the newest camera/Jon result without blocking the control loop.
3. Reject autonomous output that is stale, unavailable, from another model version, or below the configured confidence threshold.
4. Compute the center-corridor LiDAR throttle/stop policy when AEB is enabled.
5. Select manual, cruise-control, or autonomous throttle and steering according to gear/mode.
6. Apply optional IMU yaw correction, steering clamps, rate limits, servo-fault braking, and AEB hard braking.
7. Write the PCA9685 and AT8236 outputs.

## Authority Boundary

- The camera model is the sole autonomous steering source.
- LiDAR can cap forward throttle or request a hard brake; it cannot steer.
- Manual input can cancel autonomy.
- Jon never writes hardware directly.

This separation makes individual policies inspectable, but it is not a formal real-time or safety certification. Physical response, sensor coverage, and operator reaction still require field evidence.
