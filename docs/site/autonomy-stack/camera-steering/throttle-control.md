# Throttle Control

The current steering models do not control live autonomous throttle. Series 3 retains a throttle output for compatibility/training history, while Series 4 is steering-only.

## Current Policy

In autonomous mode, forward throttle comes from the center-corridor LiDAR governor when AEB is enabled:

- Full target at or beyond 1.65 m;
- Linear reduction to 60% reference by 1.25 m;
- 60% reference hold down to 1.05 m; and
- Hard stop at or inside 1.05 m.

When AEB is disabled, the LiDAR policy reports telemetry but returns full allowed throttle and no stop. In manual Drive, the operator or cruise controller supplies the requested throttle, and the same enabled LiDAR policy can cap it.

Reference throttle maps useful motion onto the physical range: 0% reference begins at 55% physical PWM, while a physical zero remains stopped. This mapping is used for the LiDAR governor and dashboard percentage. The Xbox trigger remains a direct `0.0..1.0` physical command, so manual driving still requires roughly 55% trigger before this car begins moving. Training/photo labels preserve the absolute physical command rather than the reference value.
