# Model Zoo

SidewalkPilot publishes each checkpoint as a separate Hugging Face model repository and keeps deployable artifacts under `code/ai_models/`. Version numbers describe experiments, not guaranteed monotonic improvement.

## Families

| Series | Image input | Output design | Current role |
|---|---|---|---|
| 1 | `200×66` | Direct steering regression | Original camera-steering proof |
| 2 | `200×66` | Refined direct regression; CLAHE experiment in 2.0 | Historical comparison family |
| 3.0 | `320×180` | Two-value steering/throttle regression | First large Jetson architecture |
| 3.1-3.4 | `320×180` | 9 steering classes + 9 offsets + throttle | Current Jetson hybrid family |
| 4 | Not frozen | Temporal steering research | Planning; no checkpoint exists |

## Production Selection

Regular **v3.4** is the current production model. It won the July 13, 2026 field comparison across every shadow case presented and the tested normal left/right turns. v3.4b was slightly worse, v3.3 was worse than v3.2, and v3.3b was much worse than v3.2b.

That ranking is a qualitative field verdict. The run did not record exact takeover counts, route metadata, weather, or video, so those facts are not added retroactively.

## Regular and `b`

For each training run:

- `vX.Y` is the final-epoch checkpoint;
- `vX.Yb` is the best-validation checkpoint selected during that same run.

The suffix does not mean field-best. Regular v3.4 beat v3.4b on the physical car. See [B Checkpoints](../../engineering-process/design-decisions/b-checkpoints.md).

## Selection Evidence

Aggregate MAE is not the primary ranking because the Series 3 dataset is straight-heavy. A center-collapsed model can earn good MAE and median error while missing turns. Review balanced 9-class accuracy, turn exact, turn within one class, straight exact, signed error, confusion behavior, and the fixed field route together.

- [Series 3 Model Table](series-3.md)
- [Steering Model Series](../../autonomy-stack/camera-steering/series-differences.md)
- [Shadow Robustness](../../model-evaluation/field-evaluation/shadow-robustness.md)
- [Offline vs Field](../../model-evaluation/comparisons/offline-vs-field.md)
- [Hugging Face profile](https://huggingface.co/ram-shreyas-naik-sabavat)
