# Jetson Orin Nano Runtime

The Jetson Orin Nano is the inference computer. It is linked directly to the Raspberry Pi 5 over Ethernet at `10.42.0.2:8770`; the link does not depend on Wi-Fi.

## Live Data Path

1. The Raspberry Pi 5 captures the current camera frame.
2. `AsyncJetsonSteeringClient` keeps only the newest pending frame and selected model version.
3. Jetson Orin Nano's `jetson_inference_server.py` loads the matching ONNX artifact, preprocesses the frame, and runs ONNX Runtime.
4. Jetson Orin Nano decodes the model-family-specific output and returns steering plus model telemetry.
5. The Raspberry Pi 5 accepts only a fresh response for the selected version, then applies local safety arbitration before writing actuators.

## Supported Families

- Series 1/2: one steering output, `200x66` input.
- Series 3.0/3.0b: two-output regression, `320x180` input.
- Series 3.1 through 3.4b: 19-output hybrid head.
- Series 4 PC, CF, and PCF: temporal/horizon hybrid contracts, decoded at horizon zero for live steering.

CUDA is preferred when available. CPU remains a fallback for compatibility and bench diagnosis. TensorRT is not the current live path.

## Failure Behavior

The Raspberry Pi 5 client does not block the control loop while waiting for Jetson Orin Nano. If no fresh response exists, autonomous driving does not receive a valid new steering command. Manual control and local Raspberry Pi 5 LiDAR braking remain on the Raspberry Pi 5.

Model selection is performed from the dashboard or `RC_CAR_STEERING_MODEL`; the live runtime currently defaults to v3.4.
