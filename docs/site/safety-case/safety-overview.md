# Safety Overview

SidewalkPilot moves a physical RC-scale vehicle. Its current safeguards reduce
specific risks during supervised tests; they do not constitute certification or
a complete functional-safety system.

## Implemented layers

1. **Operator control:** while the Xbox controller is connected and the Raspberry Pi 5 loop
   is responsive, steering, gas, or brake input cancels autonomy. The Share
   button requests an orderly shutdown. The operator also needs an independent
   way to cut power.
2. **LiDAR longitudinal intervention:** when AEB is enabled and fresh center-
   corridor returns are available, the policy can cap forward throttle and
   request a hard brake at 1.05 m. LiDAR never commands steering.
3. **Inference freshness:** unavailable or stale model results cause the
   autonomous path to request a hard stop. The current neural path assigns
   confidence `1.0` to accepted fresh results, so the confidence field is not a
   calibrated detector for wrong scenes.
4. **Operating procedure:** tests require line-of-sight supervision, bounded
   routes, dry conditions, and no autonomous public-road operation. The declared
   `MAX_AUTONOMOUS_SPEED_MPH` is not wired into a measured-speed governor and must
   not be described as an enforced cap.

## Known gaps

- Stale or empty LiDAR data removes obstacle intervention rather than forcing a
  stop.
- Software override depends on a connected controller and responsive process.
- Configured LiDAR thresholds do not prove physical stopping distance.
- No arbitrary-pedestrian, all-weather, or unattended-operation claim is made.
- Quantitative false-trigger, disconnect, stopping-distance, and override-latency
  records still need controlled physical tests.

## Evidence standard

Code and unit tests establish the configured arbitration logic. Physical claims
require a preserved setup, payload, speed, route, logs, video, and pass/fail
record. The July 13 model comparison selected v3.4 in the cases presented, but it
was not a safety certification or complete route benchmark.

## Related pages

- [Research Scope and Limits](../safety-and-ethics/research-scope.md)
- [Manual Override](fault-handling/manual-override.md)
- [Hazard Analysis](hazard-analysis/road-entry.md)
- [Field Testing](../testing/field-testing/overview.md)
