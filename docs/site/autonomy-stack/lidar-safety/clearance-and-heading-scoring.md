# Clearance and Heading Scoring

The live safety path uses center-corridor clearance, not LiDAR heading selection.

`center_forward_distance()` converts each valid point to forward/lateral coordinates and returns the nearest point within `LIDAR_CENTER_HALF_WIDTH_M`. `governor_target()` converts that clearance into the 1.65/1.25/1.05 m throttle-and-stop policy.

Older heading-window and sector utilities remain useful for visualization or diagnostics, and state fields for best heading still exist. They do not command steering in the current runtime. Empty windows must not be treated as proof of a safe path because missing returns can also mean sparse or stale sensing.
