# Steering Hysteresis

The mechanical reality that the wheels do not return to the same physical center depending
on whether the last move came from the left or the right, and how the runtime handles it.

## How it works

When I command the same logical center (90°), the front wheels don't always end up in the
same *physical* place — where they settle depends on which direction they came from. Coming
back from a hard left leaves them slightly different than coming back from a hard right.
This is direction-dependent return behavior. Plausible contributors include play in the
joints, linkage flex, servo return behavior, load, and surface conditions. The current
branch does not contain a traceable measurement artifact that supports one exact spread or
isolates one mechanical cause.

The current runtime uses three separate mechanisms. First, logical labels remain `0..180`.
Second, `hardware.py` maps that range to the measured reference endpoints
`48.812..131.188` and applies the current `+12` degree center trim. Third, the yaw
controller keeps direction-dependent feed-forward values (`119.5` after a left approach,
`107.8` after a right approach) and can trim them from measured yaw in `straight` mode.
The older center-preload path still exists, but its value and window are both zero.

## Why it matters

Hysteresis is a data-quality problem before it's a driving problem. If the wheels don't
sit where the label says "straight," then every "straight" training photo is captured with
the wheels slightly off — and the model learns a biased notion of center. Getting the
physical center repeatable is part of collecting clean, unbiased training data. The current
yaw-rate path (`yaw-rate-pid.md`) measures actual rotation and corrects near center, but its
field behavior remains an experimental subsystem rather than a final mechanical fix.

> Planned / not-yet-tested: a dedicated test to distinguish a *smooth pass-through 90* from
> a *flick/release snap back to 90* (which is probably driven by joystick history/velocity,
> not just the final value) is on the to-do list. Treat all steering constants as current
> tuning, not universal chassis geometry.

## Related pages

- `autonomy-stack/camera-steering/servo-output.md`
- `engineering-process/design-decisions/motor-imbalance-vs-steering-trim.md`
- `hardware/steering-servo.md`
