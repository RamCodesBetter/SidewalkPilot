# Tensor Shape

Tensor Shape documents the dimensions that move through the SidewalkPilot model. This page makes it clear what `B x C x H x W` means, why the Series 3 input is `3 x 180 x 320`, and how feature-map shape controls parameter count.

## How it works

- PyTorch image tensors use channel-first format: `batch x channels x height x width` (`B x C x H x W`).
- A single camera frame becomes `1 x 3 x 180 x 320` during Series 3 inference (`H = 180`, `W = 320`).
- Convolution layers change the channel count and, when strided, shrink the spatial size.
- `AdaptiveAvgPool2d` forces the final feature map to a fixed shape (`6 x 10` in Series 3) before the linear head, so the flattened vector length is constant.
- That flattened feature count directly sets the size of the first dense layer, which dominates the parameter count.

## Shape reference

| Concept | Meaning |
|---|---|
| `B` | Batch size (`1` at inference) |
| `C` | Channels, `3` for a color image |
| `H` | Height in pixels/features |
| `W` | Width in pixels/features |
| Series 3 input | `B x 3 x 180 x 320` |
| Series 3 pooled feature map | `B x 160 x 6 x 10` |
| Flattened Series 3 features | `160 * 6 * 10 = 9,600` |
| Series 1/2 input (runtime) | `B x 3 x 66 x 200` |
| Series 1/2 pooled feature map | `B x 64 x 4 x 8` |
| Flattened Series 1/2 features | `64 * 4 * 8 = 2,048` |

Series 3 spatial flow through the strided backbone (input `180 x 320`):

| After layer | Stride | Approx. `H x W` |
|---|---:|---|
| `Conv2d(3, 32, k5, s2, p2)` | 2 | `90 x 160` |
| `Conv2d(32, 48, k5, s2, p2)` | 2 | `45 x 80` |
| `Conv2d(48, 64, k5, s2, p2)` | 2 | `23 x 40` |
| `Conv2d(64, 96, k3, s2, p1)` | 2 | `12 x 20` |
| `Conv2d(96, 128, k3, s1, p1)` | 1 | `12 x 20` |
| `Conv2d(128, 160, k3, s1, p1)` | 1 | `12 x 20` |
| `AdaptiveAvgPool2d((6, 10))` | - | `6 x 10` (forced) |

The adaptive pool is what makes the `9,600`-length feature vector fixed: whatever the backbone produces, it is averaged down to exactly `160 x 6 x 10`.

## Why this choice

- Fixed image shapes simplify ONNX export and runtime validation. The Series 3 trainer exports input `image`, output `control_raw`, and a dynamic batch axis.
- `320 x 180` preserves far more visual detail than the older `200 x 66` Series 1/2 input while staying light enough for the Jetson.
- Documenting the shape flow prevents confusion when parameter count changes after an architecture edit - the jump from `2,048` to `9,600` flattened features is exactly why the Series 3 head is so much larger.

## Verification Note

The spatial sizes above follow directly from the checked-in convolution strides, padding, and adaptive pooling. ONNX Runtime accepts a dynamic batch dimension; live vehicle inference uses batch size `1`.

## Evidence

- `SidewalkPilotV3` and `export_onnx()` in `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`
- `STEERING_MODEL_WIDTH = 200`, `STEERING_MODEL_HEIGHT = 66` in `code/controller/current/rc_car_app/vision.py`
- `docs/cnn_parameter_visual_guide.pdf`

## Related pages

- `ai-and-models/architecture/linear-head.md`
- `ai-and-models/training-pipeline/training-script.md`
- `code-reference/training-modules.md`
