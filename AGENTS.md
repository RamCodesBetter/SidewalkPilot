# SidewalkPilot model development

## Model contracts

- Series 1 and 2 predict a continuous steering target from a camera frame. Preserve the preprocessing, output scale and steering convention of the specific export.
- Series 3.0 predicts steering and throttle. Later Series 3 networks emit steering-class logits, within-class offsets and throttle. Decode these outputs before comparing steering angles.
- Series 4 predicts hybrid steering targets without throttle. Its input history and number of output horizons depend on the variant; do not interchange model signatures.
- Series 5 performs pixel classification, not direct steering. The A/B binary baselines use MobileNetV3-Large with LR-ASPP. C/E use FP32 ConvNeXt-Tiny with a U-Net-style decoder. Preserve RGB normalization, class IDs, the ignore value and the spatial alignment between logits and reference masks.
