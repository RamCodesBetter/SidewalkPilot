# Field Testing Overview

Field testing is the final model and safety gate because offline image metrics do not reproduce closed-loop steering, vehicle inertia, linkage hysteresis, lighting transitions, or network timing.

## Model Test Method

- Use the same supervised route and comparable lighting for every candidate.
- Start and end with the current v3.4 baseline when time permits.
- Include normal left/right turns and both directions of turn under hard shadows.
- Record interventions, oscillation, late turns, edge drift, and model/link freshness.
- Preserve the matching video and CSV rather than relying on memory.

The next ordered comparison is v3.4, v4.0p, v4.0r, v4.0a, v4.0c, v3.4b, v4.0f, and v4.0g, with an optional closing v3.4 control.

## LiDAR Test Method

The current LiDAR policy has one center corridor and no steering output. With AEB enabled, verify progressive throttle capping at the 1.65 m and 1.25 m boundaries and a hard stop at 1.05 m. Run the first checks with wheels unloaded, then conduct low-speed physical obstacle tests under the real payload.

Record distance, requested throttle, actual speed, brake response, surface, battery state, and false triggers. A unit test proves policy math; only a physical run characterizes stopping performance.

## Current Results

- v3.4 was selected in the July 13 shadow/turn comparison.
- v3.3 and v3.3b regressed in that field comparison; v3.4b was slightly worse than v3.4.
- Series 4 has completed offline evaluation and runtime integration but has not yet been driven.
- The latest center-corridor LiDAR configuration still needs a preserved physical result.
