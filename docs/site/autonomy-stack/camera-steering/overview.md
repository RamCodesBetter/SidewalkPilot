# Camera Steering Overview

The Raspberry Pi 5 captures a forward frame and submits the newest image through a background worker. Jetson Orin Nano runs the selected ONNX model and returns steering plus class probabilities. The Raspberry Pi 5 rejects stale output, applies smoothing, calibration, and safety policy, and remains the only computer that writes the steering servo.

## Model Contracts

- Series 1/2: direct steering regression at 200x66.
- Series 3 v3.0: two-output regression at 320x180.
- Series 3 v3.1+: 19-value hybrid class/offset/throttle output.
- Series 4: 18-value steering horizons, optionally with causal three-target history.

## Failure Boundary

Normal Jetson Orin Nano connection and inference waits occur in the worker rather than the manual-control loop. A missing, invalid, or stale prediction is not accepted as fresh steering. Manual input and LiDAR braking remain outside the learned model. No formal worst-case scheduling guarantee is claimed.

v3.4 remains the default. The six v4.0 models are runtime-supported and have been field-tested: v4.0f was viable but mixed against v3.4, v4.0g was worse, and the four history-input models developed steering echo. The six corrective v4.1 models are trained and evaluated offline, but they are not yet registered for live use or field-tested.

See [Jetson Orin Nano Inference Link](jetson-inference-link.md), [Servo Output](servo-output.md), and [Model Choices](../../runtime-code/vision/model-choices.md).
