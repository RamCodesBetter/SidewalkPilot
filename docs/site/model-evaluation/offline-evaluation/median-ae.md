# Median Absolute Error

Median absolute error is the middle per-frame steering error after the absolute
errors are sorted. Half of the evaluated frames have a smaller error and half
have a larger error.

## Calculation

For target angles $y_i$ and predictions $\hat{y}_i$:

$$
\operatorname{MedianAE} = \operatorname{median}\left(\lvert \hat{y}_i-y_i\rvert\right)
$$

`code/test_files/evaluate_sidewalkpilot_models.py` calculates this in servo
degrees and reports it as `Med` for every compatible checkpoint.

## Interpretation

Median AE describes a typical evaluated frame and is less sensitive to a few
large misses than MAE. A median far below the MAE indicates a long error tail,
but it does not identify the cause of that tail. The difficult frames must be
located through per-class metrics, confusion matrices, dataset slices, and field
evidence.

Median AE is not a safety score. A low value can coexist with poor recall in
rare turn classes, so model selection also uses Bal9, turn metrics, straight
recall, signed error, and repeated field tests.

## Related pages

- [MAE](mae.md)
- [Bal9](bal9.md)
- [Confusion Matrix](confusion-matrix.md)
