# Model Iteration Method

SidewalkPilot treats model development as a closed physical engineering loop rather than a leaderboard exercise.

## The Loop

1. **Drive manually or under supervision.** Save camera frames with logical `0..180` steering labels and absolute physical throttle fractions.
2. **Identify a concrete failure.** Examples include diagonal-shadow following, straight collapse, turn asymmetry, stale inference, or mechanical return error.
3. **Audit the data.** Count images and labels, remove corrupt frames, inspect steering balance, and preserve correction metadata.
4. **State one hypothesis.** Change architecture, augmentation, sampling, labels, or runtime behavior for a specific reason.
5. **Train regular and `b` checkpoints.** The regular artifact is the final epoch; `b` is the best validation epoch.
6. **Evaluate compatible models.** Apply each family's input/output contract. Preserve its historical own-dataset result and use the common Series 3/4 challenge set only for the explicitly labeled cross-family comparison.
7. **Read balanced metrics.** Bal9, turn exact, turn +/-1, straight exact, MAE, median error, signed error, and confusion patterns are considered together.
8. **Deploy ONNX to the Jetson.** Confirm shape, preprocessing, decoder, and inference provider.
9. **Field-test the physical car.** Test ordinary turns plus the failure condition that motivated the model.
10. **Promote, revise, or roll back.** Preserve the reason, not only the winning filename.

## Why Time-Grouped Validation Matters

Field photos arrive like video. Neighboring frames may differ by only milliseconds. A random image split would place near-duplicates in training and validation and make memorization look like generalization.

The Series 3/4 trainer path-sorts samples, forms contiguous 100-sample windows, and reserves periodic windows. This reduces immediate-neighbor leakage, but it is not a run-group split and does not prove route independence.

## Why MAE Is Secondary

Most field data is close to straight. Predicting near 90 degrees frequently can produce an attractive MAE while failing rare but essential turns. The current report therefore applies a green-to-red rank across:

- Balanced nine-class accuracy;
- Turn exact and turn +/-1 accuracy;
- Straight exact accuracy;
- Mean and median absolute error;
- Signed steering bias.

The July 2026 v3.4/v3.4b result validates this policy: v3.4b had the lower MAE, but v3.4 had stronger turn/balance metrics and was better on the car.

## Regular and `b` Checkpoints

Every paired release answers a different question:

- `SidewalkPilot-vX.Y`: what training produced at the final epoch.
- `SidewalkPilot-vX.Yb`: which epoch the validation rule selected.

Neither suffix guarantees field superiority. Both are retained until the physical comparison decides.

## Example: v3.3 to v3.4

**Failure:** earlier models followed sharp shadow edges.

**v3.3 hypothesis:** stronger tree-shadow augmentation would improve robustness.

**Observed result:** v3.3 regressed below v3.2; v3.3b regressed much further below v3.2b.

**v3.4 response:** run a different training treatment rather than assuming that a newer checkpoint would automatically improve.

**Field result:** v3.4 completed every presented shadow case and ranked above its `b` checkpoint.

This is the desired behavior of the process: a failed experiment remains useful because it narrows the explanation and informs the next controlled change.

## Reproducible Records

Each promoted model should have:

- Trainer command and configuration;
- Dataset snapshot and source counts;
- W&B run identifier;
- Regular and best-validation artifact hashes;
- Evaluator output and report version;
- Deployment target and ONNX contract;
- Field conditions, takeovers, logs, and clips;
- Final keep/rollback decision.

Current missing metadata is tracked in the [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md).
