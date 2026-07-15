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

See [Dataset Overview](../../data/dataset-overview.md) and [Input Labels](../../ai-and-models/training-pipeline/input-labels.md).
