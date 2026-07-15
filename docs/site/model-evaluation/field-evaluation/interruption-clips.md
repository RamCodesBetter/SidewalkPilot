# Interruption Clips

Interruption clips preserve the camera frames immediately before a human changes
the car from autonomous to manual control. They support diagnosis; they do not
provide steering ground truth by themselves.

## Implemented capture path

When enabled, `InterruptionClipRecorder` buffers the JPEG frames sent to Jetson Orin Nano. On
an autonomous-to-manual transition after at least the configured autonomous
duration, a background worker writes approximately the preceding two seconds to
`~/interruption_clips/`. On shutdown, the runtime attempts to copy saved clips to
Jetson Orin Nano and keeps local files if the transfer fails.

The recorder can skip a clip if the autonomous segment is too short, no usable
frames are buffered, the video writer fails, or capture is disabled. Therefore,
"every takeover has a clip" is not a valid assumption.

## Analyzer

`code/test_files/models/clip_bucket_analyzer.py` can replay a chosen Series 3 checkpoint
over a clip and report class probabilities, decoded logical steering, and an
optional EMA trace. A raw clip has no target steering label, live IMU correction,
or measured physical wheel angle, so the tool cannot prove that a prediction was
correct or identify a root cause on its own.

## Historical study

Working notes describe a seven-clip v3.2b review from July 9-10, 2026 and associate
the takeovers with dappled shadows. The referenced analysis log is outside the
repository and the clips are not indexed in the documentation. Treat those
numbers as a historical operator analysis, not independently reproducible
evidence or a proven causal finding.

## Evidence standard for the next study

For every takeover, preserve the clip, CSV time range, model hash, route, lighting
conditions, operator reason, and physical outcome. Use the analyzer output as one
diagnostic trace and state hypotheses separately from observations.

## Related pages

- [Field Testing](../../testing/field-testing/overview.md)
- [Temporal Smoothing](../../autonomy-stack/camera-steering/temporal-smoothing.md)
- [Failure Clips](../../exhibits/media/failure-clips.md)
