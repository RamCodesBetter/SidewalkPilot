# LiDAR Throttle and Stop Priority

This page records the current division of responsibility: **the camera model owns
steering, while LiDAR may cap forward throttle or request a hard stop inside the
center safety corridor**. LiDAR no longer chooses a swerve direction.

## Decision

`lidar_avoidance.evaluate()` measures the nearest valid point in the car-relative
center corridor. `runtime.py` applies the result in both manual and autonomous
forward driving when AEB is enabled:

1. **Normal.** At or beyond 1.65 m, LiDAR does not reduce throttle.
2. **Progressive slowdown.** Between 1.65 m and 1.25 m, the maximum target falls
   linearly from 100% to 60% reference throttle.
3. **Hold.** Between 1.25 m and 1.05 m, the governor holds 60% reference throttle.
4. **Emergency stop.** At or inside 1.05 m, it requests zero throttle and full
   braking (`stop_reason = "lidar_emergency"`). Reverse is excluded.
5. **Steering.** Every steering command still comes from the driver or camera
   model. Points to the left and right are telemetry only.

The AEB controller toggle gates the entire LiDAR intervention policy. When it is
off, occupancy can still be displayed, but the policy returns no throttle cap or
stop request.

## Alternatives considered

| Option | Pros | Cons |
|---|---|---|
| Fixed LiDAR left/right swerve | reacts without needing a vision label | can choose grass or another unsafe space because LiDAR does not understand sidewalk boundaries |
| Blend LiDAR clearance into model steering | potentially smoother | two steering authorities can fight; difficult to explain and validate |
| **Model steering + LiDAR throttle/stop veto (chosen)** | one steering owner and explicit distance thresholds | cannot steer around an obstacle by itself; stopping-distance and detection coverage still need measurement |

## Reason

The previous fixed swerve rule could steer away from an obstacle without knowing
whether that side was still sidewalk. The current design keeps path choice with
the vision model and uses LiDAR only for the narrower claim it can support:
measured center-corridor clearance. The resulting throttle cap, emergency state,
and stop reason remain visible in telemetry instead of being hidden in a blended
steering command.

The current LiDAR is a Youyeetoo FHL-LD19 on USB (`/dev/ttyUSB0` via a CP2102
adapter, 230400 baud). The reader auto-discovers the port and retries in a worker
after disconnects, so serial reconnect work is not intentionally performed in the
main control loop. Missing scans remain fail-open with respect to AEB.

## How to know it worked (test gate)

- Place a controlled obstacle at each threshold and verify normal, progressive
  slowdown, 60% reference hold, and emergency braking without a LiDAR-generated
  steering change.
- Repeat in manual and autonomous forward modes with AEB on, then confirm AEB off
  leaves throttle untouched. Keep the car restrained during bench checks.
- The stop reason, center clearance, occupancy, and lane-action telemetry record
  which branch fired.
- Bench tools: `code/test_files/lidar/lidar_uart_test.py` and `code/test_files/lidar/lidar_viewer.py`.

## Related pages

- `engineering-process/design-decisions/manual-crosswalk-handoff.md`
- `testing/failures/overview.md`
- `roadmap/next-steps.md`
