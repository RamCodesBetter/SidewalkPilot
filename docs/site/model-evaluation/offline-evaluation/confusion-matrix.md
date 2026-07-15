# Confusion Matrix

The confusion matrix bins both the model's prediction and the human label into
steering classes, then tabulates every (ground class → predicted class) pair. It
is the metric that catches the failure MAE hides: a model that has quietly
collapsed toward straight or gone dead on a whole turn class. If MAE is a single
grade, the confusion matrix is the report card that shows *which* classes passed.

## How it works

The common evaluator (`code/test_files/evaluate_sidewalkpilot_models.py`) builds a
**9x9** matrix over these servo-angle classes (target on rows, prediction on
columns):

| Bucket | Servo range |
|---|---|
| HL | 0°–45° (hard left) |
| L | 45°–60° |
| L+ | 60°–75° |
| SL | 75°–85° (soft left) |
| ST | 85°–95° (straight) |
| SR | 95°–105° (soft right) |
| R | 105°–120° |
| R+ | 120°–135° |
| HR | 135°–180° (hard right) |

Alongside the matrix it reports exact-class and adjacent-class agreement,
per-class target/prediction counts, and class-balanced recall. The same nine
boundaries let direct-regression Series 1/2 checkpoints and hybrid Series 3/4
checkpoints be compared without pretending their network heads are identical.

## Why it matters

MAE can hide class collapse on a straight-heavy set. A model that predicts near
center for many turn targets may retain a competitive average error while its
turn rows drain into the ST column. The matrix exposes that behavior directly.
Strong diagonal and adjacent-class mass is necessary offline evidence, but it is
not sufficient to establish physical driving quality.

The matrix is a screening tool, not a deployment verdict. Use Bal9 and the turn
columns to find models that retain class coverage, then require a physical field
test before calling one better on the car.

## Related pages

- `model-evaluation/comparisons/mae-vs-turn-capability.md`
- `ai-and-models/architecture/steering-class-bins.md`
- `model-evaluation/offline-evaluation/within-degree-buckets.md`
