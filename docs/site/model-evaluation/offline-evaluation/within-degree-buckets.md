# Within Degree Buckets

Within-degree buckets count how many frames a model predicts within a fixed
tolerance of the human label — within 2°, 5°, 10°, and 20° of servo angle. Where
MAE compresses everything into one average, these buckets show the *shape* of the
error: how much of the set is genuinely precise versus merely "close enough."

## How it works

In `code/test_files/models/evaluate_sidewalkpilot_models.py`, `metric_block()` computes the
absolute error `ae = abs(preds - targets)` per
frame and then counts:

| Bucket | Definition |
|---|---|
| `within_2` | frames with `ae <= 2°` |
| `within_5` | frames with `ae <= 5°` |
| `within_10` | frames with `ae <= 10°` |
| `within_20` | frames with `ae <= 20°` |

The counts are cumulative (every frame within 2° is also within 5°). The PDF
report surfaces them as `<=5` and `<=10` fractions in the ranking table (e.g.
`1234/1500`) and `<=2`, `<=5`, `<=20` in the chronological growth table. These
degree buckets are distinct from the steering-*class* buckets used by the
confusion matrix — degree buckets measure numeric precision, class buckets
measure whether the right turn category was chosen.

## Why it matters

The consequence of an angle error depends on speed, geometry, actuator response,
and closed-loop history. The within-degree ladder answers a narrower offline
question: what fraction of independent evaluated frames falls within each numeric
tolerance? It can distinguish two models that share an MAE, but it does not by
itself measure confidence, temporal smoothness, or physical path error.

They also pair naturally with the other metrics: `within_2`/`within_5` describe
the low-error portion, `within_20` and max AE describe the error tail, and the gap
between buckets complements the median-versus-MAE comparison. Field testing is
still required to determine whether those errors create unstable or unsafe motion.

## Related pages

- `ai-and-models/training-pipeline/metrics.md`
- `model-evaluation/offline-evaluation/mae.md`
- `model-evaluation/offline-evaluation/confusion-matrix.md`
