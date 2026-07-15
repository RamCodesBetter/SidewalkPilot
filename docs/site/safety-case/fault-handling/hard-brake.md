# Hard Brake

Hard brake is how SidewalkPilot removes energy fast: when a stop condition fires, the
car does not coast, it clamps both motor outputs low. This page documents when the
hard brake engages and how it is applied through the AT8236 driver.

## Hazard

A center-corridor obstacle, a model/control fault, or an operator brake demand needs to stop the car
quickly. A soft, coasting stop could carry the car into an obstacle or off a curb.

## Detection and trigger

Hard braking is driven by whichever brake force reaches full scale in `update_gpio`
(`runtime.py`). The main sources:

- **AEB stop** — `is_stop_brake_condition()` reads the current
  `lidar_emergency_stop` flag, AEB is enabled, and gear is not `R`. The center-corridor
  policy sets that flag at or inside `1.05 m`.
- **Autonomous hard stop** — `apply_hard_stop_state()` sets brake force to `1.0` for a
  LiDAR emergency or when the camera/model result is unavailable, stale, or below the
  confidence gate.
- **Servo-write fault** — a failed servo write, or the configured fault window after one,
  requests the same full-scale brake response.
- **Operator brake** — full trigger pull sets `manual_brake_force` near `1.0`.

The actual clamp is `full_hard_brake = effective_brake and effective_brake_force >= 0.95`.

## Response

When `full_hard_brake` is processed, `current_motor_pwm` is forced to `0.0` without the
normal ramp, and the hardware layer puts the AT8236 into brake mode: `IN1 = 1` and
`IN2 = 1` clamps both motor outputs low on each side (per the comment in `update_gpio`).
Below the 0.95 threshold, braking ramps toward zero at a rate blended between
`COASTING_RATE = 0.6` and the active brake rate (`BRAKE_RATE = 8.0`, or
`AEB_BRAKE_RATE = 10.0` for AEB) scaled by brake force, so lighter brake pulls decelerate
proportionally instead of slamming.

## Stop condition and who triggers it

Triggered by AEB/LiDAR, the autonomous hard-stop logic, or the operator's brake
trigger. AEB overrides a manual throttle command, so the operator cannot "gas through"
an active AEB hard-stop while AEB is enabled.

## Evidence

- Code: `runtime.py` — `update_gpio` (`full_hard_brake`, `AEB_BRAKE_RATE`,
  `move_toward` ramp), `apply_hard_stop_state`, `is_stop_brake_condition`.
- Config: `config.py` — `BRAKE_RATE`, `AEB_BRAKE_RATE`, and `COASTING_RATE`.
- Hardware: AT8236 H-bridge, GPIO 19/20 (right) and 25/13 (left).
- Field evidence: a measured stopping distance (meters vs speed) is **planned /
  not-yet-measured**.

## Series 3 note

Hard braking is a Pi/hardware behavior and is independent of which steering model is
running, so Series 3 does not change it.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
