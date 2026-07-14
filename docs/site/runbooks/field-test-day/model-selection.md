# Field Model Selection

Use this procedure to compare steering checkpoints without changing hardware or route conditions between runs.

## Preconditions

- Steering trim is `+12D` and the linkage/camera position has not changed.
- The Pi, Jetson, controller, camera, and LiDAR are connected.
- The requested ONNX files exist in `code/ai_models/` on the Jetson.
- The center-corridor AEB bench test has passed, or AEB is deliberately OFF and recorded as such.
- A human operator has immediate manual takeover control.

## Procedure

1. Start the Jetson inference service, Zero 2 W dashboard service, then the Pi controller.
2. On dashboard page V2H1, select the checkpoint with D-pad up/down and confirm the `MODL` row.
3. Confirm live inference rate and that commands are not stale.
4. Drive one fixed route containing a normal left turn, normal right turn, straight section, diagonal shadow, tree shadow, and bright/dark transition.
5. Record every takeover with the model version, location, and cause.
6. Repeat without changing route direction, trim, camera, speed policy, or AEB state.
7. Stop testing a checkpoint after repeated sidewalk departure, oscillation, stale inference, or an unsafe command.

## Current Baseline

The default is regular **3.4**, selected by the July 13, 2026 field comparison. The other comparison checkpoints remain selectable:

- 3.4b: slightly worse than 3.4;
- 3.3: worse than 3.2; and
- 3.3b: much worse than 3.2b.

## Evidence To Save

- controller CSV log;
- route/date/time/weather and direction;
- model filename and AEB state;
- video for each failure;
- takeover count and causes; and
- a pass/fail row for each required turn/shadow case.

Offline metrics from `docs/steering_model_report.pdf` support diagnosis but do not override the matched-route field verdict.
