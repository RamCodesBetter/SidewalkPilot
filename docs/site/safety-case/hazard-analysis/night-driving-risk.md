# Night Driving Risk

Night operation is outside the current validated autonomy envelope. The principal
risk is a fresh, confident-looking but wrong camera steering prediction.

## Why the Existing Gates Are Insufficient

The active neural paths assign confidence `1.0` to an accepted prediction. The
runtime stops on missing or stale results, but it does not currently estimate
model uncertainty from darkness, glare, or color shift. A visible-light failure
can therefore remain fresh and pass the confidence threshold.

LiDAR range sensing does not depend on visible sidewalk texture, but it is only a
center-corridor throttle/brake layer when AEB is enabled. It does not correct
steering and should not be described as a complete night-driving safeguard.

## Evidence and Limit

An informal v3.1b field note reports generally acceptable night behavior followed
by a steering failure near orange artificial light and blocky class transitions.
That is one bounded observation, not a repeatable night-performance metric.
Temporal output smoothing has since been implemented, but the docs do not claim
that it resolved night lighting because a controlled retest is not recorded.

## Control

- Do not run unsupervised autonomy at night.
- Keep the controller in hand and use a known, controlled route for any experiment.
- Record model, light source, route, video, CSV, AEB state, and takeover cause.
- Treat artificial light, headlights, wet reflection, and direct glare as
  uncharacterized until repeated tests say otherwise.

## Related Pages

- [Lighting Limits](../operating-limits/lighting-limits.md)
- [Night Failure Demo](../../portfolio-evidence/demonstrations/night-failure-demo.md)
- [Safety Limits](../../safety-and-ethics/limits.md)
