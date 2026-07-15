# Data Claim

SidewalkPilot is trained primarily from real field images captured by the car and paired with physical steering/throttle commands.

## Verified Data State

| Dataset | Evidence |
|---|---|
| Series 1/2 | 2,224 labeled real images across 13 sources; published on Hugging Face |
| Series 3/4 | 81,237 labeled real images; shared by v3 and the S4 temporal experiments; published on Hugging Face |
| CARLA | Separate published repository of pre-generated synthetic frames |

The Series 3/4 trainer does not start CARLA. Synthetic data must already exist in a labeled folder before the trainer can use it.

## Label Integrity

- Steering is stored as an absolute 0-to-180 logical servo target.
- Throttle capture is stored as an absolute physical PWM fraction from 0.0 to 1.0.
- Hardware trim and useful-range throttle mapping remain runtime concerns and do not rewrite labels.
- Path-sorted 100-sample windows reduce adjacent-frame train/validation leakage; they do not guarantee complete capture-run separation.
- Series 4 temporal windows remain inside one source run, one split, and the configured maximum timestamp gap.

## Limits

Image count is not coverage proof. The dataset does not establish performance on every sidewalk, season, weather condition, obstacle, or lighting distribution. New collection should respond to documented field failures rather than chase a raw count target.

## Evidence

- [Hugging Face datasets](https://huggingface.co/ram-shreyas-naik-sabavat)
- `code/ai_models_datasets/series_1_and_2/`
- `code/ai_models_datasets/series_3_and_4/`
- `docs/steering_eval_current_labels.json`

See [Dataset Overview](../../data/dataset-overview.md) and [Evidence Map](../reader-paths/evidence-map.md).
