# Removed Override Steering

This page preserves an important design reversal. SidewalkPilot previously implemented a
fixed LiDAR left/right steering override. That behavior has been removed. The current
runtime never derives steering from LiDAR; the camera model owns autonomous steering.

## How it works

Current `lidar_avoidance.py` behavior:

1. Filter valid points at confidence 150 or above.
2. Measure nearest forward clearance in the center safety corridor.
3. Reduce reference throttle from 100% at 1.65 m to 60% at 1.25 m.
4. Hold 60% reference throttle until 1.05 m.
5. Request a hard brake at or inside 1.05 m.
6. Always return `steer = None`.

## Why this choice

The old rule knew where obstacle points were but did not know where the sidewalk ended.
Choosing the apparently clearer side could send the car into grass, a curb, or an unseen
hazard. A single steering owner is easier to reason about: the model handles path choice,
while LiDAR retains a deterministic longitudinal intervention.

## Key constants

| Constant | Value | Meaning |
|---|---|---|
| `LIDAR_GOV_FULL_M` | 1.65 m | Full target at or above this clearance |
| `LIDAR_GOV_STOP_M` | 1.25 m | Governor reaches its minimum moving target |
| `LIDAR_GOV_MIN_REFERENCE` | 0.60 | Minimum non-emergency reference target |
| `LIDAR_OVERRIDE_EMERGENCY_STOP_M` | 1.05 m | Hard-stop boundary |

The historical filename remains so existing documentation links do not break.

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
