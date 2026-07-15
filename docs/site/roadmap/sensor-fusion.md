# Sensor Fusion

SidewalkPilot assigns different responsibilities to each sensor rather than blending every signal into one opaque controller.

## Current Responsibilities

- Camera model: autonomous steering proposal.
- LD19 LiDAR: center-corridor forward-throttle cap and emergency-stop request when AEB is enabled.
- BN880 GPS: route and navigation state. The compass on the same board is currently a bench-only input.
- Hall sensor: wheel-speed estimate and cruise-control feedback.
- XIAO MG24 IMU: optional yaw-rate feedback for steering correction.

The IMU yaw controller is implemented in `yaw_pid.py` and integrated in `runtime.py`. Its mode and gains are configurable, and the dashboard exposes tuning/telemetry. That establishes implementation, not a measured claim that it improves every drive; a controlled before/after field result is still needed.

## Design Boundary

LiDAR does not output steering. The camera model remains the only autonomous path-selection source, while the driver can cancel autonomy. This prevents two unrelated steering systems from fighting and avoids treating empty LiDAR space as proof of safe sidewalk.

## Next Evidence

1. Preserve IMU-on versus IMU-off logs on the same route and speed.
2. Compare yaw error, steering correction, oscillation, and interventions.
3. Characterize GPS/compass behavior near trees, buildings, and vehicle electronics.
4. Keep any future obstacle-avoidance learning behind the independent LiDAR stop layer.
