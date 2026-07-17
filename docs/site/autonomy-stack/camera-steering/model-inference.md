# Model Inference

Live inference is split across the Raspberry Pi 5 and Jetson Orin Nano. The Raspberry Pi 5 owns camera capture and safety arbitration; Jetson Orin Nano owns preprocessing, model execution, and output decoding.

## Data Path

1. `WebcamVisionProcessor` captures `1280×720` `BGR888` frames from the Raspberry Pi Camera. The code declares a nominal 30 FPS target and measures the actual rate at runtime.
2. `AsyncJetsonSteeringClient.submit()` replaces any unsent frame with the newest frame and selected model version.
3. Its worker JPEG-encodes and sends the request to Jetson Orin Nano at `10.42.0.2:8770`.
4. `jetson_inference_server.py` hot-switches to the requested `SidewalkPilot-v<version>` artifact when needed.
5. Jetson Orin Nano resizes and normalizes the BGR frame, runs ONNX Runtime, decodes steering, and returns control plus telemetry.
6. The Raspberry Pi 5 consumes only a result for the selected version that is no more than `0.25 s` old.

## Capture and Preprocessing

`WebcamVisionProcessor` uses Picamera2 to capture the Raspberry Pi Camera Module 3 Wide at a nominal 1280x720, 30 FPS, in `BGR888`. The camera is mounted upside down, so the configured libcamera transform flips both axes during capture. Capture and analysis run in a daemon worker; the controller reads the newest completed frame and result rather than waiting for the camera.

Runtime preprocessing must match each checkpoint:

1. Resize with `cv2.INTER_AREA` to 200x66 for Series 1/2 or 320x180 for Series 3/4.
2. Scale pixels to `[0,1]` and normalize with `(x - 0.5) / 0.5`.
3. Transpose OpenCV BGR data from `HWC` to `CHW` and add the batch dimension.
4. Apply HSV-value CLAHE only for legacy versions 2.0 and 2.0b; all other current models use raw BGR.

Keeping BGR capture, resize, normalization, orientation, and optional CLAHE consistent with training avoids silent train/runtime distribution changes. A local frame older than 0.75 seconds is rejected by the autonomous path.

## Model Contracts

| Family | Input | Raw output | Decode |
|---|---|---|---|
| Series 1/2 | `[N,3,66,200]` | one value | steering degrees |
| Series 3.0 | `[N,3,180,320]` | two values | normalized steering and throttle |
| Series 3.1-3.4 | `[N,3,180,320]` | 19 values | 9 class logits, 9 within-class offsets, throttle |
| Series 4 PC (p/r) | image + `[N,3]` history | `[N,1,18]` | horizon-zero steering hybrid |
| Series 4 CF (f/g) | `[N,3,180,320]` | `[N,4,18]` | horizon-zero steering hybrid |
| Series 4 PCF (a/c) | image + `[N,3]` history | `[N,4,18]` | horizon-zero steering hybrid |

All recognized models normalize pixels with `(x / 255 - 0.5) / 0.5`. Versions `2.0/2.0b` additionally apply HSV-value CLAHE; current Series 3 uses raw BGR.

For the hybrid head:

```text
class = argmax(logits[0:9])
fraction = sigmoid(offset[class])
steering = bucket_low[class] + fraction * bucket_width[class]
```

The model throttle output is returned for protocol compatibility but is not used for current driving. The Raspberry Pi 5 combines model steering with its own throttle policy and center-corridor LiDAR governor.

## Steering Smoothing and Throttle Ownership

Series 3/4 hybrid steering can jump when adjacent class logits exchange the argmax. The runtime applies an exponential blend once per newly completed Jetson Orin Nano result:

```text
smoothed = 0.45 * decoded + 0.55 * previous
```

This output filter is separate from Series 4 causal target history. Smoothing changes the command sent to the car; PC/PCF history changes the information supplied to the next inference. Excessive smoothing would delay genuine turns, so it does not replace balanced training or field testing.

Current models do not control live throttle. Series 3 retains a learned throttle value for training and protocol history, while Series 4 removes it. Manual input or autonomous runtime policy supplies the requested throttle, and enabled LiDAR AEB may cap or stop forward motion. Saved training labels remain absolute physical PWM fractions rather than the dashboard's reference moving range.

## GPU Selection

Jetson Orin Nano selects CUDA plus CPU fallback when CUDA is available. It selects TensorRT plus CPU only when CUDA is unavailable but the TensorRT provider is available. This avoids a partially installed TensorRT provider causing the complete provider list to fail and retry on CPU.

## Non-Blocking and Freshness Rules

All TCP connect/send/receive and JPEG work stays in `AsyncJetsonSteeringClient`. The main loop never calls synchronous `infer()` or `poll_status()`. The worker keeps one pending frame, preventing an inference backlog.

If Jetson Orin Nano is off:

- Manual driving remains responsive;
- Temperature/IPS telemetry remains at its last cached value;
- Autonomous mode hard-stops because no fresh model command exists; and
- Connection retries continue in the worker.

Regression test:

```bash
python3 code/test_files/controller/test_async_jetson_client.py
```

The current field-selected baseline is regular v3.4. See [Steering Model Series](series-differences.md) and [Shadow Robustness](../../model-evaluation/field-evaluation/shadow-robustness.md).
