# Signed Error

Signed error is the average of `prediction - target` without taking the absolute value:

```text
signed_error = mean(prediction_deg - target_deg)
```

On the logical steering scale, positive means predictions lean right of the labels and
negative means they lean left. A value near zero means positive and negative errors cancel;
it does not mean every prediction is accurate.

## Why It Matters

MAE describes error magnitude but hides direction. A model that is +10 degrees on half the
frames and -10 degrees on the other half has substantial MAE and signed error near zero.
Signed error separates a consistently biased model from a noisy but centered one.

The same distinction matters on the car, but offline bias and physical drift are not the
same measurement. Motor imbalance, steering linkage, payload, surface, and trim can move the
physical car even when model signed error is near zero. Use the offline metric to inspect
the model and controlled hardware tests to inspect the chassis.

`code/test_files/models/evaluate_sidewalkpilot_models.py` reports signed steering error overall and
by source for all checkpoints. The current report evaluates steering only.

## Related Pages

- `model-evaluation/offline-evaluation/mae.md`
- `model-evaluation/offline-evaluation/per-dataset-breakdown.md`
- `hardware/steering-servo.md`
