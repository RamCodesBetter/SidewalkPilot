# Model Zoo

SidewalkPilot has **52 evaluated checkpoints** across four series. The live selector currently contains 46 versions through Series 4.0; the six Series 4.1 models are trained and offline-evaluated but not yet integrated. Version numbers identify experiments, not guaranteed improvements.

## Families

| Series | Image input | Output design | Parameters | Current role |
|---|---|---|---:|---|
| 1 | `200x66` | direct steering regression | 672,877 | original camera-steering proof |
| 2 | `200x66` | refined direct regression; CLAHE in 2.0/2.0b | 672,877 | historical comparison family |
| 3.0 | `320x180` | steering/throttle regression | about 5.53M | first large Jetson Orin Nano architecture |
| 3.1-3.4 | `320x180` | 9 classes + 9 offsets + throttle | 5,534,115 | field-tested family; v3.4 selected |
| 4.0 PC | `320x180` + 3 targets | one 18-value steering horizon | 5,569,186 | rejected after steering echo in field testing |
| 4.0 CF | `320x180` | four 18-value steering horizons | 5,537,560 | `4.0f` viable; complementary to v3.4 |
| 4.0 PCF | `320x180` + 3 targets | four 18-value steering horizons | 5,572,696 | rejected after steering echo in field testing |
| 4.1 PC/CF/PCF | same contracts | corrected history/future training | 5.54M | trained and offline-evaluated; integration pending |

## Field and Research State

Regular **v3.4** is the current field-selected model. It won the July 13, 2026 comparison across every shadow case presented and the tested normal left/right turns.

Series 4.0 was field-tested. `4.0f` was viable and traded two passed/failed cases with v3.4, but it did not establish a clear promotion case. `4.0p/r/a/c` repeated prior steering predictions and were rejected. Series 4.1 was trained to address that failure and still needs runtime integration and physical testing.

## Paired Checkpoints

Series 1-3 use a numeric model and a `b` checkpoint. Series 4 uses contract-specific letters:

| Run | Final | Best-validation |
|---|---|---|
| 4.0 PC | `4.0p` | `4.0r` |
| 4.0 CF | `4.0f` | `4.0g` |
| 4.0 PCF | `4.0a` | `4.0c` |
| 4.1 PC | `4.1p` | `4.1r` |
| 4.1 CF | `4.1f` | `4.1g` |
| 4.1 PCF | `4.1a` | `4.1c` |

For Series 3 and 4.0, “best validation” primarily follows steering/current-target MAE. Series 4.1 PC/PCF also includes closed-loop rollout error in checkpoint selection. Series 1/2 used validation loss. No rule makes the alternate checkpoint field-best.

## Selection Evidence

Aggregate MAE is secondary because the challenge set is straight-heavy. Review Bal9, turn exact, turn within one class, straight exact, signed error, confusion behavior, and a fixed field route together.

- [Series 3 Model Table](series-3.md)
- [Series 4 Model Table](series-4.md)
- [Bal9](../../model-evaluation/offline-evaluation/bal9.md)
- [Offline vs Field](../../model-evaluation/comparisons/offline-vs-field.md)
- [Hugging Face profile](https://huggingface.co/ram-shreyas-naik-sabavat)
