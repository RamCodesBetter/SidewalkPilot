# Model Zoo

SidewalkPilot has **46 evaluated checkpoints** across four series. Version numbers identify experiments; a newer name is not a guarantee of better driving.

## Families

| Series | Image input | Output design | Parameters | Current role |
|---|---|---|---:|---|
| 1 | `200x66` | direct steering regression | 672,877 | original camera-steering proof |
| 2 | `200x66` | refined direct regression; CLAHE in 2.0/2.0b | 672,877 | historical comparison family |
| 3.0 | `320x180` | steering/throttle regression | about 5.53M | first large Jetson architecture |
| 3.1-3.4 | `320x180` | 9 classes + 9 offsets + throttle | 5,534,115 | field-tested family; v3.4 selected |
| 4.0 PC | `320x180` + 3 targets | one 18-value steering horizon | 5,569,186 | strongest offline temporal candidate |
| 4.0 CF | `320x180` | four 18-value steering horizons | 5,537,560 | future-supervision experiment |
| 4.0 PCF | `320x180` + 3 targets | four 18-value steering horizons | 5,572,696 | combined temporal experiment |

## Field and Research State

Regular **v3.4** is the current field-selected model. It won the July 13, 2026 comparison across every shadow case presented and the tested normal left/right turns.

Series 4 is trained and runtime-supported. `4.0p` currently leads the common offline evaluation, but no Series 4 checkpoint has been field-tested. The field-selected default therefore stays on v3.4 until a controlled physical comparison says otherwise.

## Paired Checkpoints

Series 1-3 use a numeric model and a `b` checkpoint. Series 4 uses contract-specific letters:

| Run | Final | Best-validation |
|---|---|---|
| PC | `4.0p` | `4.0r` |
| CF | `4.0f` | `4.0g` |
| PCF | `4.0a` | `4.0c` |

For current Series 3/4 runs, “best validation” means lowest steering/current-target MAE during that run. Series 1/2 used validation loss. Neither rule means field-best. Regular v3.4 beat v3.4b on the car, and `4.0p` has stronger turn metrics than its lower-MAE partner `4.0r`.

## Selection Evidence

Aggregate MAE is secondary because the challenge set is straight-heavy. Review Bal9, turn exact, turn within one class, straight exact, signed error, confusion behavior, and a fixed field route together.

- [Series 3 Model Table](series-3.md)
- [Series 4 Model Table](series-4.md)
- [Bal9](../../model-evaluation/offline-evaluation/bal9.md)
- [Offline vs Field](../../model-evaluation/comparisons/offline-vs-field.md)
- [Hugging Face profile](https://huggingface.co/ram-shreyas-naik-sabavat)
