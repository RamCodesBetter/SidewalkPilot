# BatchNorm

BatchNorm documents the normalization layers placed after each convolution in the SidewalkPilot CNN. This page explains how BatchNorm stabilizes feature values during training, where it appears in the model, and whether it stays helpful for Series 3 Jetson deployment.

## How it works

- A convolution layer outputs many feature channels, and those channel activations drift as the weights change during training.
- `BatchNorm2d` normalizes each channel to roughly zero mean / unit variance over the batch, then learns two values per channel: a scale (`gamma`) and a shift (`beta`). Scale lets the network re-widen a channel it finds useful; shift lets it re-center that channel. So normalization does not throw away useful signal - the model can undo it per channel if it wants to.
- In both models it sits inside every backbone block, in Conv -> BatchNorm -> ELU order (BatchNorm comes before the activation).

## Where it appears

Series 3 (`SidewalkPilotV3`): one `BatchNorm2d` after each of the six conv layers, over channels `32, 48, 64, 96, 128, 160`.

Series 1/2 (`SteeringAutonomyV2`): one `BatchNorm2d` after each of the five conv layers, over channels `24, 36, 48, 64, 64`.

| Item | Value |
|---|---|
| Layer role | Stabilize convolution feature channels |
| Order in block | `Conv2d` -> `BatchNorm2d` -> `ELU` |
| Parameter rule | `2 * channels` (scale + shift per channel) |
| 1.x/2.x BatchNorm params | `472` |
| 3.x BatchNorm params | `1,056` |
| Runtime path | Exported in ONNX and executed by ONNX Runtime |

## Why this choice

- BatchNorm usually makes CNN training less fragile when the dataset has heavy lighting, shadow, and exposure variation - exactly the SidewalkPilot case, where the trainer deliberately injects mixed lighting, diagonal shadow bands, tree-dapple, and glare.
- The parameter cost is small relative to the dense head.
- At inference, BatchNorm uses stored running statistics rather than batch statistics. ONNX Runtime handles the exported graph on Jon.

## Planned / not yet tested

- No formal ablation has been run yet on whether removing BatchNorm hurts training loss for this dataset - it is included on the strength of the standard result, not a project-specific A/B.

## Evidence

- `SidewalkPilotV3.backbone` in `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`
- `SteeringAutonomyV2.backbone` in `code/controller/current/rc_car_app/vision.py`

## Related pages

- `ai-and-models/architecture/conv-layers.md`
- `ai-and-models/architecture/elu.md`
- `ai-and-models/architecture/tensor-shape.md`
