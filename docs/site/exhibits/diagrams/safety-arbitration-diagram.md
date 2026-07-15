# Safety Arbitration Diagram

This page diagrams how SidewalkPilot decides what reaches the motors when the camera model, the center-corridor LiDAR governor, and the human provide inputs at the same time. The camera model owns steering. LiDAR can only reduce forward throttle or request a stop, and manual input can cancel autonomous mode.

## The Priority Order

Arbitration happens inside `apply_autonomous_controls()` and `update_gpio()` in `runtime.py`, and it resolves in this order (highest authority first):

1. **Manual override (human).** Real steering, throttle, or brake input cancels autonomous mode and an active navigation route.
2. **Center-corridor emergency stop.** With AEB enabled, a valid LiDAR point at or inside `LIDAR_OVERRIDE_EMERGENCY_STOP_M = 1.05 m` requests zero throttle and full braking. Reverse is excluded from the automatic stop.
3. **Model-availability gate.** In autonomous mode, a missing model, a stale Pi camera analysis (older than 0.75 s), a missing or stale Jetson result (older than `JETSON_RESULT_MAX_AGE_SEC = 0.25 s`), or confidence below `LOW_CAMERA_CONFIDENCE = 0.25` stops the car instead of reusing a stale steering result.
4. **Camera-model steering.** If the model result is valid, it supplies the steering command. LiDAR never changes that command and never chooses a left or right escape path.
5. **Center-corridor throttle governor.** With AEB enabled, clearance at or above 1.65 m allows full throttle. From 1.65 m to 1.25 m, the target falls linearly from 100% to 60% reference throttle. It holds that minimum governed target from 1.25 m to 1.05 m, then the emergency stop takes priority. Points outside the center corridor remain dashboard telemetry only.

The 60% reference target maps to 82% physical PWM because the motors do not move in the measured 0-55% physical range. Saved throttle labels remain absolute physical fractions (`0.82` for 82%), not reference values.

## Why it is built this way

The split avoids two systems fighting over steering. The learned model handles path following and any visually learned avoidance; the geometric LiDAR layer supplies a deterministic throttle limit and close-range braking rule. These are implemented safeguards, not proof that every obstacle or stopping condition is covered.

## What this exhibit proves

That steering ownership and the current LiDAR throttle/stop thresholds are explicit in the runtime. It does not prove stopping distance, obstacle coverage, or unattended-operation safety; those require field measurements.

## Priority-ladder view

```text
human steering/throttle/brake -> cancel autonomy
                    else
enabled LiDAR emergency point -> zero throttle + full brake
                    else
missing/stale model result    -> autonomous stop request
                    else
model steering                -> steering command
enabled LiDAR governor        -> may only reduce forward throttle
```

Source anchors: `runtime.py` (`apply_autonomous_controls`, `update_gpio`, `is_stop_brake_condition`), `lidar_avoidance.py` (`evaluate`, `governor_target`), and `config.py` (thresholds).

## Related pages

- `portfolio-evidence/claims-and-proof/reproducibility-claim.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
