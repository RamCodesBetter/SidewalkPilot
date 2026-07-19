# Mean Absolute Error

Mean absolute error (MAE) is the average steering distance between prediction and target:

```text
MAE = mean(abs(prediction_deg - target_deg))
```

Both values use the logical `0..180` steering scale. Lower is better.

## Current Use

`code/test_files/models/evaluate_sidewalkpilot_models.py` computes MAE for all 52 checkpoints on
the same 6,952-frame challenge set. It also retains a separate historical 2,224-image
Series 1/2 evaluation. The report never compares values from those two datasets as if they
were interchangeable.

MAE is a supporting metric, not the primary model-ranking rule. The challenge set contains
4,741 straight-class targets and 2,211 turn targets. A model can lower average error by
staying near center while failing rare turn classes. That behavior is visible in Bal9,
turn recall, and the confusion matrix.

The current result illustrates the distinction: v4.0c has the lowest shared-set MAE, while
v4.0p has the highest Bal9. Neither offline result replaces the v3.4 field verdict.

## Interpretation

- Use MAE to compare numeric error magnitude on the same set.
- Compare MAE with median error to see whether a tail of large misses raises the mean.
- Compare it with signed error to distinguish magnitude from directional bias.
- Reject a low-MAE model if its class recalls show straight collapse.

The report evaluates steering only. It does not use Series 3 throttle error for model
selection, and Series 4 has no throttle output.

## Related Pages

- `model-evaluation/offline-evaluation/bal9.md`
- `model-evaluation/comparisons/mae-vs-turn-capability.md`
- `model-evaluation/offline-evaluation/confusion-matrix.md`
