# LiDAR Safety Overview

SidewalkPilot uses LiDAR as a longitudinal safety layer. The camera model owns steering; LiDAR can only reduce forward throttle or request a hard brake for a return directly inside the car-relative center safety corridor.

## Geometry

The dashboard displays a five-foot (`1.524 m`) scan width for context. Only its center third is active for control:

- center half-width: `0.254 m`;
- total active width: `0.508 m`;
- left/right side returns: visible telemetry only; and
- corridor frame: car/LiDAR-relative, not sidewalk-edge-relative.

For each valid point, the policy converts polar range/angle to:

```text
lateral = distance * sin(angle)
forward = distance * cos(angle)
```

A point contributes only when `forward > 0` and `abs(lateral) <= 0.254 m`. The nearest qualifying forward distance controls AEB.

## Distance Policy

| Center clearance | Physical command with AEB ON |
|---:|---|
| `>= 1.65 m` | Full requested throttle allowed |
| `1.65..1.25 m` | Proportional cap from 100% down to 55% |
| `1.25..1.05 m` | Hold 55%, the measured minimum-moving command |
| `<= 1.05 m` | Hard brake / zero throttle |

The dashboard maps physical `55..100%` to reference `0..100%`, but training/photo labels remain absolute physical commands. A 55% capture is labeled `0.55`.

## Control Priority

With AEB ON, an emergency stop overrides manual throttle, cruise control, and autonomous throttle. It does not generate steering. Servo faults and stale/unavailable model stops are separate safety mechanisms and remain active regardless of the LiDAR AEB toggle.

With AEB OFF, center occupancy is still sent to the dashboard, but LiDAR returns full throttle permission and no stop in both manual and autonomous modes.

## Implementation

- `rc_car_app/lidar.py`: UART packet acquisition and reconnect behavior.
- `rc_car_app/lidar_avoidance.py`: point validation, center geometry, governor, and emergency decision.
- `rc_car_app/runtime.py`: one policy evaluation per loop and application to manual/autonomous motor commands.
- `z2w_dashboard.py`: scan points, two center guides, four distance rungs, and the C status glyph.

Run the deterministic checks from the repository root:

```bash
python3 code/test_files/test_lidar_center_aeb.py -v
python3 code/test_files/test_z2w_lidar_layout.py -v
```

## Failure Boundary

An empty, disconnected, stale, or entirely low-confidence scan has no qualifying center point and therefore cannot trigger AEB. The LiDAR connection/status must be verified before an outdoor autonomous run; AEB ON is a policy state, not a sensor-health guarantee.
