# Field Testing Overview

Field testing is the final model and safety gate because offline image metrics do not reproduce closed-loop steering, vehicle inertia, linkage hysteresis, lighting transitions, or network timing.

## Model Test Method

- Use the same supervised route and comparable lighting for every candidate.
- Start and end with the current v3.4 baseline when time permits.
- Include normal left and right turns and both turn directions under hard shadows.
- Record interventions, oscillation, late turns, edge drift, and model/link freshness.
- Preserve the matching video and CSV rather than relying on memory.

The next comparison occurs after v4.1 live integration and steering-echo bench replay. Use v3.4 and v4.0f as controls, test the v4.1 models that pass replay, and close with v3.4 when conditions allow.

## LiDAR Test Method

The current LiDAR policy has one center corridor and no steering output. With AEB enabled, verify progressive throttle capping at the 1.65 m and 1.25 m boundaries and a hard stop at 1.05 m. Run the first checks with wheels unloaded, then conduct low-speed physical obstacle tests under the real payload.

Record distance, requested throttle, actual speed, brake response, surface, battery state, and false triggers. A unit test proves policy math; only a physical run characterizes stopping performance.

## Current Results

- v3.4 was selected in the July 13 shadow/turn comparison.
- v3.3 and v3.3b regressed in that field comparison; v3.4b was slightly worse than v3.4.
- All six v4.0 models were driven. v4.0f was viable but mixed against v3.4; v4.0g was worse; v4.0 PC/PCF models echoed prior predictions.
- Six v4.1 correction models are trained and evaluated offline but not yet integrated or driven.
- The latest center-corridor LiDAR configuration still needs a preserved physical result.

## Preflight and Run Record

Before leaving, confirm batteries, connectors, tire/linkage condition, controller pairing, model files, storage space, camera, LiDAR, GPS where needed, IMU where enabled, Jetson Orin Nano Ethernet, dashboard USB, and a physical power-cut method. Begin with wheels unloaded after hardware or control changes.

For each run preserve model version and file hash, branch/commit, route and direction, lighting/weather/surface, payload and battery state, AEB state, start/end time, distance, CSV, clips, and every takeover with cause and location. Define pass/warn/fail before driving.

The next Series 4 comparison should begin with v3.4, include v4.0f as a second control, and then test only the v4.1 models that pass integration and replay checks. A closing v3.4 repeat helps reveal route, battery, or lighting changes during the session.

## Manual Takeovers

A takeover begins when qualifying manual input cancels autonomy. `code/test_files/data/takeover_log_report.py` identifies valid manual disengagements, their cause, run time, preceding autonomous duration, speed, steering, throttle/brake state, AEB state, and model when the CSV payload contains it. Review that output with video and available navigation telemetry to identify route position or node; the utility does not infer a node that the log did not record. Claims should not exceed what the preserved files can reconstruct.
