# Label Schema

## Physical Targets

| Field | Range | Meaning |
|---|---:|---|
| steering | 0-180 degrees | absolute logical servo target |
| throttle | 0.0-1.0 | absolute physical PWM fraction; `0.55` means 55% |
| image/path | string | frame identity |
| source/run | string | capture provenance |
| timestamp/order | ordered value | split and temporal-sequence membership |

Hardware center trim does not rewrite the steering label. Runtime useful-range throttle mapping does not rewrite the captured absolute throttle label.

## Family Use

- Series 1/2 train steering-only direct regression.
- Series 3 accepts steering and throttle labels; steering-focused runs may give throttle loss zero.
- Series 4 uses steering only and derives previous/future targets from ordered labels.

Series 4 future targets are supervision only. They are not runtime inputs.

## Validation

Reject missing images, non-numeric/out-of-range values, duplicate conflicts without an explicit correction rule, and temporal windows that cross a run/split/gap boundary. Corrections override matching base labels and should retain provenance.

## Corrections and Review

A correction record must identify the image, provide the reviewed logical steering target, and retain enough source context to explain why it overrides the base row. Optional repeat weighting is a training decision and must not be confused with label confidence.

Duplicate filenames from different runs require path/run disambiguation. Exact duplicate rows may be deduplicated during snapshot construction only when the retained record and count are documented. Conflicting labels require visual/run review; averaging them hides the disagreement.

Examples requiring review include unreadable images, missing throttle in a Series 3 record, nonnumeric values, out-of-range steering, a correction with no matching image, and a temporal window that crosses a capture gap. Tools may report or clamp a value, but automated acceptance is not evidence that the label is behaviorally correct.

See [Dataset Overview](../../data/dataset-overview.md), [Relabeling Workflow](../../data/relabeling/workflow.md), and [Training Pipeline](../../ai-and-models/training-pipeline/overview.md).
