# Historical Dataset Metrics

Dataset metrics must be tied to a named snapshot. Counts from one dataset must not be presented as though they describe another.

## Series 1/2 Snapshot

| Item | Value |
|---|---:|
| JPG images | 2,224 |
| label entries | 2,224 |
| sources | 13 |
| steering range | 0-180 degrees |

Recorded coarse distribution:

| Range | Count |
|---|---:|
| 0-45 | 69 |
| 45-75 | 128 |
| 75-85 | 281 |
| 85-95 | 678 |
| 95-105 | 547 |
| 105-135 | 311 |
| 135-180 | 199 |

## Series 3/4 Snapshot

| Item | Value |
|---|---:|
| labeled real images | 81,237 |
| model input | 320x180 |
| split | path-sorted contiguous 100-sample windows; approximately every Nth window held out |
| Series 4 temporal history/future | three steps where applicable |

The common evaluator uses a frozen 6,952-frame challenge subset from this dataset. That is an evaluation subset, not a third training dataset.

## Drift Rule

Never delete or trim data to force a count to match. Identify the source-level delta, document whether it is a correction, addition, exclusion, or corruption, and create a new snapshot when membership changes.

See [Dataset Overview](../../data/dataset-overview.md) and [Active Label Set](active-label-set.md).
