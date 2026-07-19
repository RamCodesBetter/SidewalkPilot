# Successful Autonomous Runs

A successful run is evidence for a specific model, route, lighting condition, payload, and software revision. It is not a universal autonomy claim.

## Required Record

- Model version and Git commit;
- Route, time, and lighting;
- AEB and IMU/yaw-controller state;
- Complete video and CSV log;
- Interventions and their causes; and
- Dashboard/model-link health.

The strongest current field result is the July 13 comparison in which regular v3.4 handled the tested normal and harsh-shadow turn cases better than v3.3, v3.3b, and v3.4b. `4.0f` later completed useful cases and was viable, but its complementary failures versus v3.4 did not justify promotion.

During autonomy, the camera model owns steering. LiDAR can cap throttle or emergency-brake in the center corridor when enabled; it does not steer around an obstacle.
