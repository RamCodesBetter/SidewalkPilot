# Where It Cannot Run

Autonomous operation is excluded in these conditions:

- Roadways or vehicle traffic;
- Uncontrolled pedestrian traffic;
- Stairs, ledges, curbs/drop-offs, or other negative obstacles;
- Surfaces or slopes outside controlled testing;
- Blocked, dark, glared, or otherwise unreadable camera views;
- Routes where the operator cannot maintain line of sight and immediate takeover;
- Missing/stale model output; and
- A missing or unhealthy LiDAR stream when the test depends on AEB.

The 2D LiDAR scans a horizontal plane and cannot reliably detect a downward drop. It also cannot identify the sidewalk boundary. The camera model can fail outside its training distribution. These are operating limits, not problems solved by adding a larger model.

With a healthy LiDAR and AEB enabled, the current runtime can slow and stop for center-corridor returns. It does not find an escape side or steer around them.
