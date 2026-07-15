# Conv Layers

Conv Layers documents the visual feature-extraction backbone of the SidewalkPilot CNN. This page explains what convolution filters are, how channel counts grow through the network, and why Series 3 uses a wider and deeper convolution backbone than the 1.x/2.x model.

## How it works

- A convolution layer learns small filters (kernels) that slide over the image and respond to local patterns.
- Early filters learn basic edges, contrast changes, and texture; later filters combine those into higher-level route features like a curb line or a grass/sidewalk boundary.
- Each `Conv2d` in these models is followed by `BatchNorm2d` and an `ELU` activation (the Conv -> BN -> ELU block).
- Strided convolutions (`stride=2`) also downsample: they shrink the spatial size while growing the channel count, so the network trades resolution for richer features as it goes deeper.
- Series 3 uses more channels than 1.x/2.x, so it can represent more visual patterns before the linear head makes a control decision.

## Backbone layer tables

Series 1/2 (`SteeringAutonomyV2`, backbone = `131,820` params):

| Layer | Conv | Kernel | Stride | Padding | Out channels |
|---|---|---:|---:|---:|---:|
| 1 | `Conv2d(3, 24)` | 5 | 2 | 0 | 24 |
| 2 | `Conv2d(24, 36)` | 5 | 2 | 0 | 36 |
| 3 | `Conv2d(36, 48)` | 5 | 2 | 0 | 48 |
| 4 | `Conv2d(48, 64)` | 3 | 1 | 0 | 64 |
| 5 | `Conv2d(64, 64)` | 3 | 1 | 0 | 64 |

Series 3 (`SidewalkPilotV3`, backbone = `469,392` params):

| Layer | Conv | Kernel | Stride | Padding | Out channels |
|---|---|---:|---:|---:|---:|
| 1 | `Conv2d(3, 32)` | 5 | 2 | 2 | 32 |
| 2 | `Conv2d(32, 48)` | 5 | 2 | 2 | 48 |
| 3 | `Conv2d(48, 64)` | 5 | 2 | 2 | 64 |
| 4 | `Conv2d(64, 96)` | 3 | 2 | 1 | 96 |
| 5 | `Conv2d(96, 128)` | 3 | 1 | 1 | 128 |
| 6 | `Conv2d(128, 160)` | 3 | 1 | 1 | 160 |

Channel progression at a glance:

| Series | Channel progression |
|---|---|
| 1.x/2.x | `3 -> 24 -> 36 -> 48 -> 64 -> 64` |
| 3.x | `3 -> 32 -> 48 -> 64 -> 96 -> 128 -> 160` |

Per-layer parameter count follows `out_channels * in_channels * kernel_h * kernel_w + out_channels`.

## Why this choice

- Sidewalk driving has many visual edge cases: grass/sidewalk boundaries, driveway slopes, shadows, curb curves, glare, and low-light frames. The whole shadow-augmentation stack in the Series 3 trainer (mixed lighting, diagonal shadow bands, tree-dapple patterns, road-edge shadow) exists because these are the hard cases.
- Wider conv layers give the model more capacity to learn those patterns before committing to a control decision.
- The backbone is only `469,392` params in Series 3 - about 8.5% of the model. The width buys visual capacity cheaply; the parameter cost lives in the head (see `linear-head.md`), not here.
- Keeping the backbone convolutional keeps inference efficient on Jetson Orin Nano/TensorRT compared with a heavier transformer-style stack.

## Planned / not yet captured

- Exact spatial shape after each Series 3 conv block is documented on `tensor-shape.md`; feature-map visualizations have not been generated yet.
- The wider Series 3 channels were an engineering change; no recorded channel-width ablation isolates their effect from data, loss, and augmentation changes.

## Evidence

- `SidewalkPilotV3.backbone` in `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`
- `SteeringAutonomyV2.backbone` in `code/controller/current/rc_car_app/vision.py`
- `docs/cnn_parameter_visual_guide.pdf`

## Related pages

- `ai-and-models/architecture/cnn.md`
- `ai-and-models/architecture/batchnorm.md`
- `ai-and-models/architecture/linear-head.md`
