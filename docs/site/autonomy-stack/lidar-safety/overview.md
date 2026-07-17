# Overview

The LiDAR safety layer is SidewalkPilot's deterministic center-corridor throttle and
braking guard. It sits outside the neural steering model: the model owns steering,
while LiDAR can reduce forward throttle or request a stop when AEB is enabled. It does
not select a swerve direction.

The sensor is a Youyeetoo FHL-LD19 spinning LiDAR running at 230400 baud. It currently
connects over USB through a CP2102 UART-to-USB Adapter (auto-resolved from
`/dev/serial/by-id/*CP2102*`, falling back to `/dev/ttyUSB*`); an earlier wiring used the
Raspberry Pi 5's GPIO UART at `/dev/ttyAMA2`. A background reader thread
(`rc_car_app/lidar.py`, `LidarParser`) parses the raw packet stream into a full 360-degree
scan of `LidarPoint` objects, and the main control loop in `rc_car_app/runtime.py` pulls
the latest scan once per iteration with `get_latest_scan()`.

## How it works

The pipeline is a straight line from bytes to a throttle or braking decision:

1. **Parse.** `LidarParser` reads the LD19's 47-byte packets, extracts 12 measurement
   points each (angle, distance in mm, confidence), and accumulates them into a rolling
   full scan. Parsing, stale-scan handling, and reconnect behavior are documented on the
   [Hardware LiDAR](../../hardware/lidar.md) page.
2. **Measure the center corridor.** `lidar_avoidance.center_forward_distance()` filters
   invalid or low-confidence points and returns the nearest positive-forward point within
   the center safety corridor.
3. **Govern throttle.** At 1.65 m or more the target remains full. It falls linearly to
   60% reference throttle at 1.25 m and holds that target to 1.05 m.
4. **Brake.** At or inside 1.05 m, AEB requests zero throttle and full braking. This
   applies in manual and autonomous forward driving when AEB is enabled; reverse is
   excluded. See [AEB](aeb.md).

The same computed policy is reused within a control iteration, so autonomous command
generation and final hardware arbitration do not intentionally interpret two different
scans. Operator input can cancel autonomy while the controller and Raspberry Pi 5 loop are responsive.

## Why this choice

Keeping close-range throttle and braking outside the neural network makes those decisions
explicit and auditable. The model handles visual path choice; LiDAR handles measured
center clearance. This is a bounded design decision, not a claim that LiDAR detects every
hazard or that the configured threshold guarantees a particular stopping distance.

## Why LiDAR Does Not Steer

SidewalkPilot previously implemented fixed left/right LiDAR steering and later a
left/center/right lane concept. Both were removed. Obstacle points can identify occupied
range but cannot prove where the sidewalk ends or whether apparently empty space is grass,
a curb, sparse sensing, or another unseen hazard. The current policy therefore always
returns no steering command. One autonomous steering owner is easier to reason about: the
camera model chooses the path, while LiDAR constrains only longitudinal motion.

The runtime also does not cluster or classify LiDAR points. It uses the nearest valid return
inside one center corridor. This intentionally simple rule cannot distinguish a person from
a wall, estimate object width, or establish that adjacent space is traversable.

## Layer priority

| Layer | Role | Priority |
|---|---|---|
| Manual override | Cancel autonomy and drive via Xbox controller | Highest software authority while controller/loop are responsive |
| LiDAR / AEB | Center clearance, throttle cap, emergency brake | Overrides forward throttle only |
| Camera model | Autonomous steering command | Sole autonomous steering owner |

## Current status

Implemented and wired into the runtime: packet parsing, background reconnect, center
occupancy, progressive throttle governance, AEB braking, and dashboard telemetry. The
earlier left/center/right swerve-through design was removed because range points alone do
not identify a safe sidewalk boundary. Quantitative stopping-distance, false-positive,
and obstacle-coverage evidence is still to be collected.

## Related pages

- `autonomy-stack/architecture/data-flow.md`
- `autonomy-stack/lidar-safety/aeb.md`
- `hardware/lidar.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
