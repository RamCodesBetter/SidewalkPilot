# LiDAR Safety Demonstration

This demonstration should show the current center-corridor throttle governor and emergency brake without implying obstacle classification or steering avoidance.

## Procedure

1. Restrain the car or unload the drive wheels.
2. Confirm AEB is enabled and the LiDAR stream is healthy.
3. Move a broad stationary test target through the 1.65 m, 1.25 m, and 1.05 m boundaries.
4. Record dashboard state, CSV telemetry, requested throttle, and brake output.
5. Repeat at controlled low speed only after the static policy test passes.

## Expected Behavior

- Above 1.65 m: no LiDAR throttle reduction.
- 1.65 m to 1.25 m: progressive reduction.
- 1.25 m to 1.05 m: 60% reference hold.
- At or inside 1.05 m: zero throttle and hard brake.
- Steering remains unchanged by LiDAR throughout.

The demo passes only when the observed behavior and recorded distance agree repeatedly. A source-code test alone is not a physical stopping result.
