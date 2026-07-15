# Model Inference

Live inference is split across the Raspberry Pi 5 and Jetson Orin Nano. The Pi owns camera capture and safety arbitration; Jon owns preprocessing, model execution, and output decoding.

## Data Path

1. `WebcamVisionProcessor` captures `1280×720` `BGR888` frames from the Pi Camera. The code declares a nominal 30 FPS target and measures the actual rate at runtime.
2. `AsyncJetsonSteeringClient.submit()` replaces any unsent frame with the newest frame and selected model version.
3. Its worker JPEG-encodes and sends the request to Jon at `10.42.0.2:8770`.
4. `jetson_inference_server.py` hot-switches to the requested `SidewalkPilot-v<version>` artifact when needed.
5. Jon resizes and normalizes the BGR frame, runs ONNX Runtime, decodes steering, and returns control plus telemetry.
6. The Pi consumes only a result for the selected version that is no more than `0.25 s` old.

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

The model throttle output is returned for protocol compatibility but is not used for current driving. The Pi combines model steering with its own throttle policy and center-corridor LiDAR governor.

## GPU Selection

Jon selects CUDA plus CPU fallback when CUDA is available. It selects TensorRT plus CPU only when CUDA is unavailable but the TensorRT provider is available. This avoids a partially installed TensorRT provider causing the complete provider list to fail and retry on CPU.

## Non-Blocking and Freshness Rules

All TCP connect/send/receive and JPEG work stays in `AsyncJetsonSteeringClient`. The main loop never calls synchronous `infer()` or `poll_status()`. The worker keeps one pending frame, preventing an inference backlog.

If Jon is off:

- Manual driving remains responsive;
- Temperature/IPS telemetry remains at its last cached value;
- Autonomous mode hard-stops because no fresh model command exists; and
- Connection retries continue in the worker.

Regression test:

```bash
python3 code/test_files/test_async_jetson_client.py
```

The current field-selected baseline is regular v3.4. See [Steering Model Series](series-differences.md) and [Shadow Robustness](../../model-evaluation/field-evaluation/shadow-robustness.md).
