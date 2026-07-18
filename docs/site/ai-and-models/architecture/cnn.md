# Convolutional Steering Networks

SidewalkPilot uses custom convolutional networks to map a forward camera frame to a steering command. The model does not contain LiDAR braking or GPS routing. The Raspberry Pi 5 applies those rules separately before commanding the steering servo and motors.

## Architecture Families

| Family | Image tensor | Parameters | Learned output |
|---|---:|---:|---|
| Series 1/2 | `3x66x200` | 672,877 | direct steering regression |
| Series 3 v3.0 | `3x180x320` | approximately 5.53M | steering + throttle regression |
| Series 3 v3.1+ | `3x180x320` | v3.4: 5,534,115 | 9 logits + 9 offsets + throttle |
| Series 4 PC | image + three targets | 5,569,186 | one 18-value steering horizon |
| Series 4 CF | image | 5,537,560 | four 18-value steering horizons |
| Series 4 PCF | image + three targets | 5,572,696 | four 18-value steering horizons |

Parameter counts are weights, not megabytes. FP32 normally stores each parameter in four bytes, so approximately 5.5 million parameters require approximately 22 MB before small graph metadata. That is why the Series 3/4 ONNX files are about 22.1-22.3 MB.

## Series 1/2 Network

The early network uses five convolution stages with channels `3 -> 24 -> 36 -> 48 -> 64 -> 64`, adaptive pooling to `64x4x8`, and a compact dense steering head. The output is bounded by `tanh` and decoded around logical center:

```text
steering = 90 + output_scale * tanh(raw)
```

Series 1 uses an 86-degree output scale and Series 2 uses 85 degrees. These compact models established the first complete image-to-steering pipeline. The current unified runtime loads them on the Jetson Orin Nano, just like Series 3 and 4.

## Series 3 Visual Network

Series 3 uses channels `3 -> 32 -> 48 -> 64 -> 96 -> 128 -> 160`, adaptive pooling to `160x6x10`, and dense layers that turn the 9,600 pooled features into the output head.

v3.0 uses the early two-output contract. v3.1 and later use the hybrid steering head:

```text
probabilities = softmax(9 logits)
class = argmax(probabilities)
fraction = sigmoid(offset_for_selected_class)
steering = class_low + fraction * (class_high - class_low)
```

The class term encourages commitment to turns; the local offset preserves a continuous servo command instead of limiting output to nine fixed angles. The implementation can select `argmax(logits)` directly because softmax preserves their ordering and therefore selects the same class.

## Series 4 Visual and Temporal Network

Series 4 reuses the Series 3 convolutional backbone. Adaptive pooling and dense layers produce a 256-value image feature.

PC and PCF normalize the three prior targets as `(steering - 90) / 90`, encode them through `3 -> 32 -> 64`, concatenate the 64 history features with the 256 image features, and fuse `320 -> 128 -> 64`.

CF has no history branch and maps `256 -> 64`. Each horizon then uses its own `64 -> 18` output layer. The extra history/fusion layers explain why PC/PCF are slightly larger than CF; the four small horizon heads add much less capacity than the dense visual encoder.

## Input Preprocessing

- Frames originate as OpenCV BGR arrays from Raspberry Pi 5 camera capture.
- Each family resizes to its required dimensions.
- Pixel values are normalized to the range expected by the matching trainer.
- Series 2 v2.0/v2.0b can use the documented CLAHE path; other current models use raw BGR preprocessing plus training-time augmentation.

Preprocessing is part of the model contract. A checkpoint evaluated with the wrong resize, channel order, or decoder is not a valid comparison.

## Deployment

All current model families run on the Jetson Orin Nano GPU. Series 1/2 use PyTorch with CUDA; Series 3/4 use ONNX Runtime with CUDA. CPU execution is retained only as a diagnostic fallback. TensorRT is not part of the current field runtime.

See [Series 3 Hybrid Head](series-3-hybrid-head.md), [Series 4 Temporal Experiments](series-4-plan.md), and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).
