# Field Evaluation

Field evaluation is the final model-selection gate because offline metrics do not fully represent a moving, mechanically loaded car on real sidewalks.

## What It Catches

- shadow edges mistaken for sidewalk boundaries;
- center-biased models that obtain low MAE by avoiding real turns;
- left/right asymmetry hidden by aggregate metrics;
- delayed or stale Jetson commands;
- oscillation introduced by class changes or smoothing; and
- interactions among steering trim, weight, linkage play, and model output.

## Current Result

The July 13, 2026 comparison selected regular v3.4 over v3.4b, v3.3, and v3.3b. See [Shadow Robustness](shadow-robustness.md) for the recorded qualitative result and its missing metadata.

## Minimum Comparison Procedure

1. Use the same car hardware, `+12D` steering trim, camera position, route, and direction for every checkpoint.
2. Confirm the Jetson reports the requested model on the `MODL` dashboard row.
3. Drive the same normal left turn, normal right turn, straight shadow crossing, diagonal shadow, and mixed bright/dark segment.
4. Record takeover count and reason rather than relying only on memory.
5. Stop a model comparison after any repeated sidewalk departure or unsafe command.
6. Save the controller CSV, video, conditions, model name, and AEB state.

The LiDAR AEB test is separate from the steering comparison. LiDAR may slow or stop for a center obstacle, but it never supplies steering, so a successful swerve is evidence about the camera model only.

## Evidence Sources

- `logs/log_<timestamp>.csv`: runtime state and AEB/model telemetry.
- `docs/steering_model_report.pdf`: reproducible offline comparison.
- `code/test_files/evaluate_sidewalkpilot_models.py`: report generator.
- Field video/interruption clips: visual evidence of path behavior.
