# Motor Balance vs Steering Trim

An observed pull does not identify its own cause. SidewalkPilot therefore keeps steering
mapping, IMU yaw correction, and left/right motor scaling as separate controls.

## Current state

```python
LEFT_MOTOR_PWM_SCALE = 1.0
RIGHT_MOTOR_PWM_SCALE = 1.0
```

No per-side motor compensation is active. The steering layer separately maps logical
`0..180` commands through characterized reference limits and a +17-degree checked-in trim.
The IMU yaw controller is another independent, experimental correction path.

## Diagnostic sequence

1. Reproduce the pull on the same flat surface, payload, tire pressure, battery state, and
   throttle.
2. Verify the raw servo command and physical wheel center from both approach directions.
3. Compare left/right wheel behavior with the chassis safely supported.
4. Change only one control at a time and repeat the same condition.

If changing one motor scale changes the path consistently while wheel center remains fixed,
that supports a motor-balance interpretation. If the physical wheel center changes with
approach direction, that supports a steering/linkage interpretation. Weight, flex, and
surface effects remain possible until controlled out.

## Why the controls remain separate

- Servo trim changes front-wheel angle.
- Motor scale changes one side's drive command.
- Yaw feedback changes steering from measured motion.

Combining them without a controlled test can hide one fault with another adjustment and
make labels or calibration harder to interpret.

## Related pages

- `runtime-code/hardware/motor-pwm.md`
- `autonomy-stack/camera-steering/steering-hysteresis.md`
- `hardware/motors.md`
