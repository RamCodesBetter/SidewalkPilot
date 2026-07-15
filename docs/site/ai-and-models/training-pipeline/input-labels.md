# Input Labels

Each usable field sample pairs an image with the physical command associated with that frame.

| Field | Stored convention |
|---|---|
| steering | absolute logical degrees, 0 left / 90 center / 180 right |
| throttle | absolute physical PWM fraction, 0.0 to 1.0 |
| source/run | capture provenance and sequence boundary |
| timestamp/order | ordering used by split and temporal windows |

The trainer normalizes values internally. Storage stays in readable physical units. Steering trim and motor dead-zone mapping are not baked into the dataset.

## Series Use

- Series 1/2 learn steering only.
- Series 3 accepts steering and throttle; current steering-focused experiments can set throttle loss to zero.
- Series 4 learns steering only and derives previous/future targets from ordered records.

For Series 4, future targets are supervision. The deployed model never receives a future label.

## Collection Caution

A manually driven photo can be an imitation target. A photo captured under autonomous control must be labeled according to the intended data policy rather than automatically treated as human ground truth. Corrections must retain image/source provenance.

## Validation

Reject missing files, invalid numeric values, unreviewed duplicate conflicts, and temporal windows that cross a run, split, or excessive timestamp gap.

See [Label Schema](../../data-governance/labeling/label-schema.md) and [Dataset Overview](../../data/dataset-overview.md).
