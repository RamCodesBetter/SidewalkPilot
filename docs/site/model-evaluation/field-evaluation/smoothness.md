# Steering Smoothness

Smoothness separates rapid command changes from a consistently wrong steering trend. Both
can look abrupt on the car, but they require different evidence and may have different
causes.

## Measurements

For a time-aligned clip and CSV interval, record:

- Decoded steering change per inference;
- Selected-class switches;
- Steering standard deviation and maximum step;
- Physical servo command after runtime smoothing and calibration;
- Vehicle speed and manual takeover; and
- The same statistics with and without an explicitly stated smoothing rule.

The Series 3/4 runtime applies an exponential moving average to completed Jon steering
results with `STEERING_SMOOTH_ALPHA = 0.45`. The clip analyzer can replay a Series 3 clip
with a matching alpha, but it does not reproduce IMU correction, actuator mechanics, or the
full closed-loop trajectory.

## Evidence Limit

An earlier draft quoted exact switch counts and standard deviations from a v3.2b clip set.
The analysis log and source clips are not indexed in the repository, so those numbers are
not reported as a verified study result. Smoothing is implemented, but the project has not
preserved a controlled physical before/after test proving a particular comfort, wear, or
safety improvement.

For the Series 4 comparison, use synchronized video and CSV data to distinguish model-output
changes from servo linkage, yaw correction, control-loop timing, and vehicle motion.

## Related Pages

- [Temporal Smoothing](../../autonomy-stack/camera-steering/temporal-smoothing.md)
- [Interruption Clips](interruption-clips.md)
- [Model Retest Plan](../../testing/field-testing/model-retest-plan.md)
