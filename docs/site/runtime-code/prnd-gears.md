# PRND Gears

The car uses a simple Park / Reverse / Neutral / Drive gear state machine, modeled on a
real automatic transmission. The current gear gates what the throttle is allowed to do,
so the same trigger pull means "go forward", "go backward", or "nothing" depending on
the gear.

## How it works

The gears are `GEARS = ["P", "R", "N", "D"]` in `config.py`, and `state["gear_mode"]`
starts at `"P"`. The two shift buttons step through the list one position at a time
(indices are clamped, so you cannot shift past P or past D):

- **Shift up** (RB, `SHIFT_UP_BUTTON = 7`): `GEARS[min(index + 1, len)]` → P→R→N→D.
- **Shift down** (LB, `SHIFT_DOWN_BUTTON = 6`): `GEARS[max(index - 1, 0)]` → D→N→R→P.

Every shift also clears any manual brake force and cancels cruise control, so a gear
change is always a clean transition.

`update_gpio()` in `runtime.py` translates the gear into motor behavior each loop:

| Gear | Behavior in `update_gpio()` |
|---|---|
| **P** (Park) | PWM forced to 0, brake forced on (`effective_brake_force = 1.0`), PID reset. The car is held stopped. |
| **R** (Reverse) | Desired PWM is `-throttle` (drives the motors in reverse); manual brake still applies. AEB stop logic is intentionally skipped in R so you can back away from an obstacle. |
| **N** (Neutral) | PWM 0, brake off, PID reset. Motors coast; the car is free to roll. |
| **D** (Drive) | Forward driving. Throttle maps to forward PWM, unless cruise control is active (then a PID targets `cc_target_speed`) or the brake is held. Cruise control can only be toggled in D. |

Enabling autonomous driving forces the gear to `D` (and cancels cruise). The negative
sign of `current_motor_pwm` is what selects direction downstream: positive drives the
forward motor pins, negative drives the reverse pins — see
[Motor PWM](hardware/motor-pwm.md).

## Why it matters

Gating throttle behind a gear keeps intent explicit and safe. You cannot accidentally
lurch forward while parked, reverse is a deliberate shift rather than a hidden trigger
combo, and Park actively brakes rather than just coasting. Because Reverse deliberately
bypasses the forward AEB stop, the driver stays in control when deliberately backing up
toward something the LiDAR would otherwise treat as a blocking obstacle. Cruise control
and autonomy are both scoped to Drive, so higher-level speed control can assume forward
motion.

## Failure symptom

If the car will not move when the throttle is pulled, the most common cause is being in
P or N. The current gear is shown on dashboard page 1 (the `PRND` letters, with the
active gear highlighted), which is the fastest way to confirm the transmission state.

## Related pages

- `runtime-code/runtime-loop.md`
- `runtime-code/controller-mapping.md`
- `runtime-code/hardware/motor-pwm.md`
