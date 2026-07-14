# SidewalkPilot Series 4

Status: **planning scaffold; no Series 4 model has been trained or deployed.**

Series 4 is a parallel research track started on July 13, 2026. It must not destabilize the proven Series 3 runtime. Series 3.4 remains the field-selected production baseline while Series 4 experiments are developed, evaluated, and rejected or promoted independently.

## Starting Evidence

The first Series 4 experiment must beat the behavior that matters in the field, not merely lower aggregate MAE:

- v3.4 handled every shadow case presented in the July 13 field comparison.
- v3.4 also completed the tested normal left and right turns.
- v3.4b was slightly worse in the same comparison.
- v3.3 was worse than v3.2, and v3.3b was much worse than v3.2b.
- The v3.3 result demonstrates that stronger or more complex augmentation can regress control even when it appears theoretically useful.

## Compatibility Baseline

Until a Series 4 design explicitly changes one of these contracts, experiments should preserve:

| Contract | Series 3 baseline |
|---|---|
| Camera input | BGR image resized to `320x180` |
| Steering labels | Absolute logical servo degrees, `0..180`, with `90` straight |
| Throttle labels | Absolute physical command, `0..1`; `0.55` stays `0.55` in labels |
| Validation | Time-segment split, never random adjacent-frame leakage |
| Deployment | ONNX on the Jetson Orin Nano |
| Safety ownership | Model steers; center-corridor LiDAR only slows or stops |
| Production baseline | `SidewalkPilot-v3.4.onnx` |

The current Series 3.1+ output contract is 19 raw values: nine steering-class logits, nine within-class offsets, and one throttle value. Series 4 may retain or replace this head, but the choice must be documented before implementation so the trainer, evaluator, ONNX export, and Jetson decoder change together.

## First Milestone

1. Freeze a reproducible v3.4 replay on the current Series 3 validation split.
2. Write a one-sentence Series 4 hypothesis and identify the single architectural change being tested.
3. Add the model in this directory without changing the Series 3 trainer.
4. Add output-shape, decode, forward-pass, ONNX-export, and Jetson-load smoke tests.
5. Train regular `4.0` and best-epoch `4.0b` checkpoints with identical data and reporting.
6. Compare turn recall, class balance, signed error, MAE, and shadow subsets.
7. Field-test against v3.4 before adding any `4.x` choice to the live controller.

## Decisions Still Open

- Single-frame versus temporal input.
- Hybrid bucket head versus a different steering representation.
- Backbone family and parameter/latency target.
- Whether throttle remains an output while the dataset is approximately 95% full-throttle.
- FP16/INT8 goals and the calibration set used on the Jetson.

An open decision is not an invitation to silently inherit Series 3 behavior. Each decision must be made explicitly in the first Series 4 design record.

## Promotion Gate

A Series 4 checkpoint is not production-ready until it:

- loads and runs on the Jetson at the required camera rate;
- does not collapse straight or turn classes;
- matches or beats v3.4 on the fixed shadow and normal-turn route;
- preserves model-command freshness and manual takeover behavior;
- passes the center-corridor AEB bench test; and
- has a field log with conditions, failures, and takeover count.
