# Jetson Orin Nano Inference Link

The Raspberry Pi 5 and Jetson Orin Nano communicate over a private point-to-point Ethernet network. The Raspberry Pi 5 is `10.42.0.1`; Jetson Orin Nano is `10.42.0.2:8770`. The link does not depend on Wi-Fi or internet access.

## Frame Path

1. The Raspberry Pi 5 camera thread captures the latest OpenCV BGR frame.
2. The asynchronous client keeps only the newest pending frame, preventing a backlog.
3. The client JPEG-encodes the frame and sends the selected model version plus JPEG bytes over persistent TCP.
4. Jetson Orin Nano resolves/hot-swaps the requested artifact.
5. Jetson Orin Nano decodes JPEG, resizes and normalizes according to model input shape, and runs ONNX Runtime.
6. Jetson Orin Nano decodes the current steering target and sends 15 floats: steering, throttle placeholder, CPU/GPU temperatures, inference rate/time, and nine current-horizon bucket probabilities.
7. The Raspberry Pi 5 accepts only a result for the active model that is no more than 0.25 seconds old.
8. The Raspberry Pi 5 applies steering EMA, LiDAR/AEB arbitration, yaw/hardware mapping, and actuator commands.

JPEG encoding, connection attempts, sends, receives, and status polls run in `AsyncJetsonSteeringClient`, not the 60 Hz hardware/controller loop. If camera frame production exceeds inference, pending frames are replaced rather than queued. This keeps commands recent.

## Model Contracts

| Model | ONNX input | ONNX output | Live decode |
|---|---|---|---|
| S1/S2 | image | one degree value | direct steering |
| S3.0 | image | `[batch,2]` | unit steering/throttle |
| S3.1+ | image | `[batch,19]` | 9 logits + 9 offsets + throttle |
| S4 PC | image + 3-target history | `[batch,1,18]` | horizon 0; no throttle |
| S4 CF | image | `[batch,4,18]` | horizon 0; no throttle |
| S4 PCF | image + 3-target history | `[batch,4,18]` | horizon 0; no throttle |

For PC/PCF, Jetson Orin Nano owns the causal history because it serializes inference. The history initializes to `[90,90,90]`, appends each decoded current target, and resets on model load/switch, reconnect, or status-only/manual periods.

## GPU Selection

Jetson Orin Nano prefers `CUDAExecutionProvider` with CPU fallback. TensorRT is selected only when CUDA is unavailable. Registering both CUDA and a partially installed TensorRT provider can make ONNX Runtime reject the complete provider list and silently fall back to CPU; the runtime avoids that failure mode.

Series 4 was verified against all six real ONNX exports with CUDA active. The output shapes and probability sums matched their contracts.

## Failure Boundary

Jetson Orin Nano network and inference work runs outside the main controller loop, so the Raspberry Pi 5 does not intentionally wait on Jetson Orin Nano before processing controller/GPIO work. In autonomy, no accepted fresh result produces confidence zero and a hard-stop request. This is a conservative software response, not proof of a complete fail-safe system. The Raspberry Pi 5 remains final software authority over motors, steering mapping, AEB, and cleanup.

See [Raspberry Pi 5 + Jetson Orin Nano Compute Split](../../engineering-process/design-decisions/pi-plus-jetson-compute-split.md) and [Runtime Loop](../../runtime-code/runtime-loop.md).
