# Camera Steering Overview

The Pi captures a forward frame and submits the newest image through a background worker. Jon runs the selected ONNX model and returns steering plus class probabilities. The Pi rejects stale output, applies smoothing, calibration, and safety policy, and remains the only computer that writes the steering servo.

## Model Contracts

- Series 1/2: direct steering regression at 200x66.
- Series 3 v3.0: two-output regression at 320x180.
- Series 3 v3.1+: 19-value hybrid class/offset/throttle output.
- Series 4: 18-value steering horizons, optionally with causal three-target history.

## Failure Boundary

Normal Jetson connection and inference waits occur in the worker rather than the manual-control loop. A missing, invalid, or stale prediction is not accepted as fresh steering. Manual input and LiDAR braking remain outside the learned model. No formal worst-case scheduling guarantee is claimed.

v3.4 is the field-selected baseline. All six Series 4 models are runtime-supported but await physical comparison.

See [Jetson Inference Link](jetson-inference-link.md), [Servo Output](servo-output.md), and [Model Choices](../../runtime-code/vision/model-choices.md).
