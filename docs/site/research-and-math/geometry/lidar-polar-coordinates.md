# LiDAR Polar Coordinates

The LD19 reports angle, distance, and confidence. SidewalkPilot converts each valid point into car-relative lateral and forward coordinates for the center-corridor safety policy.

## Coordinate Conversion

The parser reports angles in `0..360` degrees with zero mounted forward. Safety code normalizes angles above 180 degrees by subtracting 360, then computes:

```text
lateral = distance * sin(angle)
forward = distance * cos(angle)
```

A point is in the governed corridor when:

- `forward > 0`;
- `abs(lateral) <= LIDAR_CENTER_HALF_WIDTH_M`; and
- The point is valid, nonzero, and has confidence at least `LIDAR_MIN_CONFIDENCE`.

`center_forward_distance()` returns the nearest such forward distance. `governor_target()` maps that distance to the current 100%-to-60%-reference throttle policy, and `evaluate()` requests a hard stop at the emergency boundary.

The older front/left/right/back sector function still supplies general dashboard direction/distance telemetry. It does not choose autonomous steering. The current safety decision comes from `rc_car_app/lidar_avoidance.py` and one center corridor.

## Limits

An empty sector or corridor does not prove that the sensor is healthy. Sensor freshness and point arrival must be checked separately before a run. LiDAR range points also do not identify the sidewalk boundary, which is why the removed swerve logic was not retained.
