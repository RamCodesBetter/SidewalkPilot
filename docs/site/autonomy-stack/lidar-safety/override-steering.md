# LiDAR Steering Override

**Current status: removed from production.**

Older SidewalkPilot revisions divided the sidewalk corridor into L/C/R bands and emitted `SWR` or `CRP` commands. That design could steer toward grass because LiDAR knew obstacle position but did not know the actual sidewalk boundaries. It also allowed autonomous steering intervention to occur before the AEB toggle was checked.

The current design has one center safety corridor and no LiDAR steering output. `lidar_avoidance.evaluate()` always returns `steer=None`; the camera model remains the only autonomous steering source.

## Why It Was Removed

- Side clearance is not proof that the clear space is sidewalk.
- A reactive swerve can conflict with the camera model's path estimate.
- Steering and emergency braking have different safety responsibilities.
- Regular v3.4 demonstrated strong enough shadow/turn behavior to keep path selection with vision.
- One center slowdown/stop corridor is easier to test deterministically.

## Current Responsibility Split

| Subsystem | Responsibility |
|---|---|
| Camera model on Jetson | Choose steering path |
| LiDAR on Pi | Limit forward throttle and hard-stop in center corridor |
| Operator | Enable/disable AEB, take over, and stop the run |
| Servo-fault/model-freshness checks | Stop for control-system faults independently of AEB |

Historical swerve prototypes may remain under copied controller snapshots or old experiment files, but the live files under `code/controller/current/` contain no `SWR`, `CRP`, `swerve_left`, or `swerve_right` control path.
