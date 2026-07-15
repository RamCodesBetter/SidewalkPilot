# Steering Class Bins

Series 3 v3.1+ and Series 4 divide absolute steering into nine classes:

| Class | Range (degrees) | Meaning |
|---|---:|---|
| HL | 0-45 | hard left |
| L | 45-60 | left |
| L+ | 60-75 | stronger left |
| SL | 75-85 | soft left |
| ST | 85-95 | straight |
| SR | 95-105 | soft right |
| R | 105-120 | right |
| R+ | 120-135 | stronger right |
| HR | 135-180 | hard right |

The model predicts one class and one local offset for each class. Runtime selects the largest logit, applies sigmoid to that class's offset, and maps the resulting fraction into the class range.

Training/sampling code can also use coarser groupings for weighting or reports. A sampling bucket is not necessarily the model's output class, so metric pages must name which grouping they use.

The common evaluator uses these nine classes for Bal9, turn exact, turn +/-1, ST exact, and confusion matrices.

See [Series 3 Hybrid Head](series-3-hybrid-head.md) and [Bal9](../../model-evaluation/offline-evaluation/bal9.md).
