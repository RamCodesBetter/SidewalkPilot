# Max AE

Max absolute error is the single worst steering miss on the whole label set: the
one frame where the model's prediction was furthest, in servo degrees, from the
human-corrected label. It is the tail-risk metric — the number that says "on its
worst frame, how wrong was this model?"

## How it works

The current evaluator computes it in `metric_block()` as `max(abs(preds - targets))` in
servo degrees (`code/test_files/models/evaluate_sidewalkpilot_models.py`). Because steering is clamped to
`0..180`, the theoretical ceiling is 180° (predicting hard-right on a hard-left
frame), but a realistic worst case is a full turn class in the wrong direction.

## Why it matters

MAE and median AE describe the model on average and on a typical frame; max AE
describes the model on its worst day. For a vehicle that shares sidewalks, the
worst-case miss matters more than the average one — a model that is 3° off on
average but 90° off on one curve can still steer the car into a curb. Max AE is
the fastest way to notice that a model has a catastrophic blind spot hiding
behind good averages.

In practice I use it as a red flag rather than a ranking key: two models can have
nearly identical MAE, but the one with a much larger max AE is the riskier
deploy. It is worth pairing with the per-dataset breakdown to find *which* run
the worst frame came from — a high max AE concentrated in a known field-failure
subset (turns, shadows) is a targeted data problem, not random noise.

## Related pages

- `ai-and-models/training-pipeline/metrics.md`
- `model-evaluation/offline-evaluation/mae.md`
- `model-evaluation/offline-evaluation/per-dataset-breakdown.md`
