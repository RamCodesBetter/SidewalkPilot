# Jetson Orin Nano Inference Link

The Raspberry Pi 5 and Jetson Orin Nano communicate over a private point-to-point Ethernet network. The Raspberry Pi 5 is `10.42.0.1`; Jetson Orin Nano is `10.42.0.2:8770`. The link does not depend on Wi-Fi or internet access.

## Frame Path

1. The Raspberry Pi 5 camera thread captures the latest OpenCV BGR frame and records its monotonic timestamp and sequence number.
2. The asynchronous client keeps only the newest pending frame, preventing a backlog.
3. The client binds the frame to the steering history that existed at capture time, JPEG-encodes it, and sends the selected model version, optional history, and JPEG bytes over persistent TCP.
4. Jetson Orin Nano loads or switches to the requested model.
5. Jetson Orin Nano decodes the JPEG, resizes and normalizes it for the selected family, and runs PyTorch CUDA for Series 1/2 or ONNX Runtime CUDA for Series 3/4.
6. Jetson Orin Nano decodes the current steering target and sends 15 floats: steering, throttle placeholder, CPU/GPU temperatures, inference rate/time, and nine current-horizon bucket probabilities.
7. The Raspberry Pi 5 accepts only a result for the active model that is no more than 0.08 seconds (80 ms) old and no more than two camera frames (40 ms at the nominal 50 FPS target) behind.
8. The Raspberry Pi 5 applies steering EMA, LiDAR/AEB rules, yaw correction, hardware mapping, and the final steering and motor commands.

JPEG encoding, connection attempts, sends, receives, and status polls run in `AsyncJetsonSteeringClient`, not the 50 Hz hardware/controller loop. If camera frame production exceeds inference, pending frames are replaced rather than queued. This keeps commands recent.

## Model Contracts

| Model | Runtime input | Raw model output | Live decode |
|---|---|---|---|
| S1/S2 | image | one normalized steering value | direct steering around logical center |
| S3.0 | image | `[batch,2]` | unit steering/throttle |
| S3.1+ | image | `[batch,19]` | 9 logits + 9 offsets + throttle |
| S4 PC | image + 3-target history | `[batch,1,18]` | horizon 0; no throttle |
| S4 CF | image | `[batch,4,18]` | horizon 0; no throttle |
| S4 PCF | image + 3-target history | `[batch,4,18]` | horizon 0; no throttle |

For PC/PCF, the Raspberry Pi 5 sends three causal steering targets with every inference request. While the operator is driving, those are sampled from manual steering; during autonomy, accepted model predictions advance the sequence. The samples retain the approximately 10 Hz spacing used by Series 4 training even though camera capture, inference requests, and control target 50 Hz. The client selects only samples at or before the frame's capture timestamp. This lets the first autonomous frame begin from the car's actual steering motion instead of an artificial `[90,90,90]` history and prevents a newer command from being attached to an older image. The Jetson Orin Nano validates the received history length before using it.

## GPU Selection

Jetson Orin Nano prefers `CUDAExecutionProvider` with CPU fallback. TensorRT is selected only when CUDA is unavailable. Registering both CUDA and a partially installed TensorRT provider can make ONNX Runtime reject the complete provider list and silently fall back to CPU; the runtime avoids that failure mode.

All six Series 4.0 and all six Series 4.1 ONNX models are registered in the live selector. Series 4.1 still requires supervised physical testing before any field-performance claim.

## Failure Boundary

Jetson Orin Nano network and inference work runs outside the main controller loop, so the Raspberry Pi 5 does not intentionally wait on Jetson Orin Nano before processing controller/GPIO work. In autonomy, no accepted fresh result produces confidence zero and a hard-stop request. This is a conservative software response, not proof of a complete fail-safe system. The Raspberry Pi 5 applies the accepted prediction, steering mapping, enabled AEB policy, steering/motor outputs, and shutdown cleanup.

See [Raspberry Pi 5 + Jetson Orin Nano Compute Split](../../engineering-process/design-decisions/pi-plus-jetson-compute-split.md) and [Runtime Loop](../../runtime-code/runtime-loop.md).
