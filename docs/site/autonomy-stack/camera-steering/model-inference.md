# Model Inference

Production inference is split across the Raspberry Pi 5 and Jetson Orin Nano. The Pi owns camera capture and safety arbitration; Jon owns preprocessing, model execution, and output decoding.

## Data Path

1. `WebcamVisionProcessor` captures `1280×720` `BGR888` frames from the Pi Camera at a target 30 FPS.
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
| Series 3.1-3.4 | `[N,3,180,320]` | 19 values | 9 class logits, 9 selected-class offsets, throttle |

All recognized models normalize pixels with `(x / 255 - 0.5) / 0.5`. Versions `2.0/2.0b` additionally apply HSV-value CLAHE; current Series 3 uses raw BGR.

For the hybrid head:

```text
class = argmax(logits[0:9])
fraction = sigmoid(offset[class])
steering = bucket_low[class] + fraction * bucket_width[class]
```

The model throttle output is returned for protocol compatibility but is not used for current driving. The Pi combines model steering with its own throttle policy and center-corridor LiDAR governor.

## GPU Selection

ONNX Runtime provider order on Jon is CUDA, TensorRT, then CPU. Startup logs state the selected providers. A CPU-only warning means the installed ONNX Runtime build cannot access the Jetson GPU.

## Non-Blocking and Freshness Rules

All TCP connect/send/receive and JPEG work stays in `AsyncJetsonSteeringClient`. The main loop never calls synchronous `infer()` or `poll_status()`. The worker keeps one pending frame, preventing an inference backlog.

If Jon is off:

- manual driving remains responsive;
- temperature/IPS telemetry remains at its last cached value;
- autonomous mode hard-stops because no fresh model command exists; and
- connection retries continue in the worker.

Regression test:

```bash
python3 code/test_files/test_async_jetson_client.py
```

The current production selection is regular v3.4. See [Steering Model Series](series-differences.md) and [Shadow Robustness](../../model-evaluation/field-evaluation/shadow-robustness.md).
