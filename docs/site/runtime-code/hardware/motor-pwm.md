# Motor PWM

The drive motors are four `PWMOutputDevice` channels created by `Hardware._init_pwm(...)` in `code/controller/current/rc_car_app/hardware.py` and driven through the Yahboom AT8236 H-bridge. Each of the two brushed drive motors uses two GPIO pins (a forward and a backward channel), so direction and speed are both set purely by which channel carries PWM and at what duty cycle.

## How it works

At startup `Hardware` opens four PWM channels at 1000 Hz with an initial duty of 0:

| Channel attribute | GPIO pin | Config constant |
|---|---|---|
| `motor_right_fwd` | 19 | `MOTOR_RIGHT_FWD_PIN` |
| `motor_right_bwd` | 20 | `MOTOR_RIGHT_BWD_PIN` |
| `motor_left_fwd` | 25 | `MOTOR_LEFT_FWD_PIN` |
| `motor_left_bwd` | 13 | `MOTOR_LEFT_BWD_PIN` |

The runtime sets speed and direction in `apply_controls` (`runtime.py`). Each loop it takes the smoothed motor command `state["current_motor_pwm"]` in `[-1, 1]`, takes its absolute value as `pwm_val`, and scales each side independently:

```
left_pwm  = clamp(pwm_val * LEFT_MOTOR_PWM_SCALE,  0, 1)
right_pwm = clamp(pwm_val * RIGHT_MOTOR_PWM_SCALE, 0, 1)
```

It then zeroes all four channels and drives exactly the ones needed:

- Forward (`current_motor_pwm > 0.001`): `motor_right_fwd = right_pwm`, `motor_left_bwd = left_pwm`.
- Reverse (`current_motor_pwm < -0.001`): `motor_right_bwd = right_pwm`, `motor_left_fwd = left_pwm`.
- Hard brake (brake force ≥ 0.95): all four channels driven to `1.0`. On the AT8236, IN1=1 and IN2=1 puts a motor in brake mode, clamping both outputs low instead of coasting.

Note the deliberate fwd/bwd pairing across sides (right-forward with left-backward): this is how the wiring/mounting orientation is compensated so both wheels roll the car the same direction.

Except for the full hard-brake branch, the command is rate-limited before this stage:
`move_toward(...)` ramps `current_motor_pwm` toward the desired PWM using `ACCEL_RATE`
when speeding up and `COASTING_RATE` / `BRAKE_RATE` when slowing. The runtime selects
`AEB_BRAKE_RATE` for an AEB stop, but AEB also sets full brake force, so the hard-brake
branch forces PWM directly to zero before the ramp is reached.

### Per-side scaling experiment

`LEFT_MOTOR_PWM_SCALE` and `RIGHT_MOTOR_PWM_SCALE` allow a controlled motor-balance experiment. Both are `1.0` now, so no per-side compensation is active. A pull with centered steering does not by itself prove motor imbalance; linkage geometry, wheel loading, surface slope, servo mapping, and motor output are separate candidates that need isolation.

## Why this choice

- Two-pin-per-motor control lets one H-bridge channel do forward, reverse, coast, and active brake with only duty-cycle changes.
- Independent left/right scale constants make motor balance testable without changing steering labels.
- 1000 Hz PWM is fast enough that the motors see a smooth average voltage rather than audible/visible stepping.

## Failure symptom

If a motor channel fails to open, `Hardware` falls back to dummy devices and prints `Running in simulation mode.` The runtime can continue updating state while no physical output occurs. For a one-sided pull, first reproduce it on a consistent surface and isolate steering-center, wheel-load, and motor-output effects before changing a scale.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
