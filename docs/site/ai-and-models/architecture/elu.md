# ELU

ELU is the hidden-layer activation used throughout the SidewalkPilot CNN families. This page describes what it does and distinguishes an implemented architecture choice from a measured claim about model quality.

## How it works

- Without a nonlinear activation, stacked layers collapse into a single linear map - no matter how many you stack, they can only draw a straight decision boundary. The activation is what lets the network learn curved, real-world features.
- ELU (Exponential Linear Unit) passes positive values through unchanged and smoothly bends negative values toward a small negative floor (`exp(x) - 1` for `x < 0`) instead of hard-clipping them to zero like ReLU.
- For finite negative inputs, ELU has a nonzero derivative rather than ReLU's exactly flat negative region. The derivative still approaches zero for very negative inputs.
- Series 1/2, Series 3, and Series 4 all use `nn.ELU(inplace=True)` in their hidden convolutional and dense paths.

## Where it appears

| Item | Value |
|---|---|
| Activation | `nn.ELU(inplace=True)` |
| Used after | hidden convolutional and dense layers |
| Series 1/2 output | one `Tanh` value, decoded into steering degrees |
| Series 3 output | raw 19-value hybrid head; decoding applies softmax/sigmoid operations |
| Series 4 output | raw 18-value steering head per prediction horizon |
| Main reason | nonlinear feature learning with a smooth, non-dead negative side |

A quick before/after for intuition:

| Pre-activation `x` | ELU output |
|---:|---:|
| `2.0` | `2.0` |
| `0.5` | `0.5` |
| `0.0` | `0.0` |
| `-0.5` | `-0.39` |
| `-2.0` | `-0.86` |

## Why this choice

- ELU supplies the nonlinearity needed between learned linear operations and preserves a gradient for negative finite inputs.
- It is compatible with the project's PyTorch-to-ONNX export and ONNX Runtime CUDA deployment path on Jon.
- The current evidence shows that models containing ELU train and deploy. It does not show that ELU itself causes smoother steering or better field behavior.

## Planned / not yet tested

- No activation ablation against ReLU, LeakyReLU, GELU, or SiLU is recorded for this dataset. ELU is the inherited project default, not the winner of a measured comparison.

## Evidence

- `SteeringAutonomyV2` in `code/ai_models_datasets/series_1_and_2/sidewalkpilot_trainer.py`
- `SidewalkPilotV3` in `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`
- `SidewalkPilotV4` in `code/ai_models_datasets/series_3_and_4/series_4_common.py`
- Runtime model definitions in `code/controller/current/rc_car_app/vision.py`

## Related pages

- `ai-and-models/architecture/batchnorm.md`
- `ai-and-models/architecture/tanh-output.md`
- `research-and-math/machine-learning/loss-function.md`
