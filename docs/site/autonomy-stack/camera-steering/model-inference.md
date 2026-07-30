# Model Inference

The Jetson Orin Nano is the AI brain for current live inference: it owns Series 1-4
preprocessing, GPU model execution, and output decoding. The Raspberry Pi 5 owns camera
capture and final safety rules. Current autonomy stops if a fresh, matching Jetson Orin Nano
result is unavailable.

## Data Path

1. `WebcamVisionProcessor` uses the full-field `2304×1296` IMX708 sensor mode and captures `1280×720` `BGR888` output frames. The code requests a nominal 50 FPS and measures the actual rate at runtime.
2. `AsyncJetsonSteeringClient.submit()` replaces any unsent frame with the newest frame and selected model version.
3. Its worker JPEG-encodes and sends the request to Jetson Orin Nano at `10.42.0.2:8770`.
4. `jetson_inference_server.py` hot-switches to the requested `SidewalkPilot-v<version>` model when needed.
5. Jetson Orin Nano resizes and normalizes the BGR frame, runs PyTorch CUDA for Series 1/2 or ONNX Runtime CUDA for Series 3/4, decodes steering, and returns the result plus telemetry.
6. The Raspberry Pi 5 consumes only a result for the selected version that is no more than `0.08 s` (80 ms) old and no more than two camera frames (40 ms at the nominal 50 FPS target) behind.

The camera, controller, and request path share a 20 ms target period, but they are asynchronous workers rather than one hardware-locked clock. Jetson Orin Nano is request-driven and runs each received frame as soon as possible. The measured camera FPS, inference IPS, capture-to-result latency, and frame-lag telemetry determine the actual rate. Capture timestamps and sequence checks prevent a late result or newer steering-history sample from being treated as if it belonged to another frame.

## Capture and Preprocessing

`WebcamVisionProcessor` uses Picamera2 to pin the Raspberry Pi Camera Module 3 Wide to its full-field 2304x1296 sensor mode and output 1280x720 at a nominal 50 FPS in `BGR888`. The camera is mounted upside down, so the configured libcamera transform flips both axes during capture. Capture runs in a daemon worker; the controller reads the newest completed frame and result rather than waiting for the camera.

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
| Series 4 PC | image + `[N,3]` history | `[N,1,18]` | horizon-zero steering hybrid |
| Series 4 CF | `[N,3,180,320]` | `[N,4,18]` | horizon-zero steering hybrid |
| Series 4 PCF | image + `[N,3]` history | `[N,4,18]` | horizon-zero steering hybrid |

All recognized models normalize pixels with `(x / 255 - 0.5) / 0.5`. Versions `2.0/2.0b` additionally apply HSV-value CLAHE; current Series 3 uses raw BGR.

For the hybrid head:

```text
probabilities = softmax(logits[0:9])
class = argmax(softmax(logits[0:9]))
fraction = sigmoid(offset[class])
steering = bucket_low[class] + fraction * bucket_width[class]
```

The decoder applies softmax first and then applies argmax to the resulting probabilities. The separately named probability vector is included in model telemetry.

Series 1-3 retain a model throttle field, while Series 4 supplies a zero placeholder in the response protocol. Neither controls current driving. The Raspberry Pi 5 combines model steering with its own throttle policy and center-corridor LiDAR governor.

## Steering Smoothing and Throttle Ownership

Series 3/4 hybrid steering can jump when adjacent class logits exchange the argmax. The runtime applies an exponential blend once per newly completed Jetson Orin Nano result:

```text
smoothed = 0.45 * decoded + 0.55 * previous
```

This output filter is separate from Series 4 causal target history. Smoothing changes the command sent to the car; PC/PCF history changes the information supplied to the next inference. History retains the approximately 10 Hz spacing used during Series 4 training and is selected at the camera-capture timestamp. Excessive smoothing would delay genuine turns, so it does not replace balanced training or field testing.

Current models do not control live throttle. Series 3 retains a learned throttle value for training and protocol history, while Series 4 removes it. Manual input or autonomous runtime policy supplies the requested throttle, and enabled LiDAR AEB may cap or stop forward motion. Saved training labels remain absolute physical PWM fractions rather than the dashboard's reference moving range.

## GPU Selection

The Jetson Orin Nano runs Series 1/2 through PyTorch CUDA and Series 3/4 through ONNX Runtime CUDA. CPU execution is retained for diagnosis, but field startup should confirm that the GPU provider loaded. TensorRT is not part of the current field path.

## Non-Blocking and Freshness Rules

All TCP connect/send/receive and JPEG work stays in `AsyncJetsonSteeringClient`. The main loop never calls synchronous `infer()` or `poll_status()`. The worker keeps one pending frame, preventing an inference backlog.

If Jetson Orin Nano is off:

- Manual driving remains responsive;
- Temperature/IPS telemetry remains at its last reported value;
- Autonomous mode hard-stops because no fresh model command exists; and
- Connection retries continue in the worker.

Regression test:

```bash
python3 code/test_files/controller/test_async_jetson_client.py
```

The current field-selected baseline is regular v3.4. See [Steering Model Series](series-differences.md) and [Field Evaluation](../../model-evaluation/field-evaluation/overview.md).
