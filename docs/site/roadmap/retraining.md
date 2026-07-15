# Retraining

Retraining is triggered by a documented field gap, not by the desire to create another version number.

## Current Baseline

v3.4 is field-selected. The shared Series 3/4 dataset contains 81,237 labeled real images. Series 4 has already completed PC, CF, and PCF training on that unchanged dataset; those models need field testing before another data/model cycle is justified.

## Retrain Trigger

A new run should start only when at least one condition is true:

- A repeatable field failure identifies a missing scene/turn/lighting class;
- Label audit finds a correctable data problem;
- A controlled architecture hypothesis can be compared on the frozen split;
- Deployment constraints require a measured optimization experiment.

## Required Gate

1. Preserve the failing clip/log and model hash.
2. Define what new data or architecture change should fix it.
3. Freeze the comparison data and command.
4. Train final/best artifacts and export ONNX.
5. Run the common evaluator.
6. Re-drive the original failure plus ordinary left/right controls.

Bal9 and turn metrics order candidates, but field behavior decides promotion. MAE remains one diagnostic column rather than the sole objective.

## Current Open Model Work

- Field-test v4.0p/r/a/c/f/g against v3.4.
- Inspect autoregressive smoothness for PC/PCF.
- Use the result to decide whether causal history deserves a Series 4 continuation.
- Collect new turn-in-shadow data only if the test identifies a repeatable remaining gap.

See [Model Retest Plan](../testing/field-testing/model-retest-plan.md) and [Series 4 Models](../ai-and-models/model-zoo/series-4.md).
