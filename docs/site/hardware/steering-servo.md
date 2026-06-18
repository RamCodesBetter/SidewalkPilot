# Steering Servo

## Measured Steering Calibration

The steering linkage is not mechanically symmetric at the full servo endpoints.
A measured fit in the Desmos graph
[Fix Servo Trim Graph](https://www.desmos.com/calculator/sdwx6h3vpx)
found that the useful left-side endpoint is around real servo `26.4558 deg`,
not real servo `0 deg`.

Runtime, dashboard display, CSV telemetry, and photo labels use a logical
steering range. The hardware adapter converts that logical value to the real
PCA9685 servo command only at the final write:

- Logical steering `0 deg` maps to real servo `26.4558 deg`.
- Logical steering `90 deg` maps to real servo `90 deg`.
- Logical steering `180 deg` maps to real servo `180 deg`.
- Public runtime state and labels remain logical `0..180`; the real command is
  not duplicated in logs.

The conversion is piecewise so center remains physically centered:

```python
LEFT_REAL_LIMIT_DEG = 26.4558
CENTER_SERVO_DEG = 90.0
RIGHT_REAL_LIMIT_DEG = 180.0


def logical_to_real_servo_deg(logical_deg: float) -> float:
    logical = max(0.0, min(180.0, float(logical_deg)))
    if logical <= CENTER_SERVO_DEG:
        return CENTER_SERVO_DEG - (
            ((CENTER_SERVO_DEG - logical) / CENTER_SERVO_DEG)
            * (CENTER_SERVO_DEG - LEFT_REAL_LIMIT_DEG)
        )
    return logical
```

This gives up unnecessary full-lock left steering, but sidewalks do not require
tight turns. The goal is smoother, more symmetric steering labels for the v3.0
training dataset while keeping hardware calibration hidden behind the steering
adapter.

TODO:

- [ ] Add page-specific notes for `hardware/steering-servo.md` after inspecting the real project files.
- [ ] Cross-link `Steering Servo` to the most relevant code, data, testing, and safety pages.
- [ ] List the exact component names and model numbers where known.
- [ ] Document wiring, voltage, connector, and mounting details.
- [ ] Add what software file reads from or commands this hardware.
- [ ] Add the calibration or setup steps needed before a run.
- [ ] Add bench-test steps and expected output.
- [ ] Add common physical failure modes and symptoms.
- [ ] Add safety limits for power, motion, heat, or outdoor testing.
- [ ] Add the exact source path, artifact path, or hardware component name.
- [ ] Add the command or procedure needed to reproduce the result.
- [ ] Add expected inputs and outputs.
- [ ] Add the settings, flags, constants, or calibration values that control it.
- [ ] Add known failure modes and how they appear in logs, video, or field behavior.
- [ ] Add validation steps and pass/fail criteria.
