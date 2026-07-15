# Model Switching

The dashboard can cycle all 46 registered Series 1-4 version names while the controller process remains running. Selection behavior differs between local Raspberry Pi 5 inference and the current camera-only/Jetson Orin Nano path.

## Registered choices

`STEERING_MODEL_VERSIONS` in `vision.py` contains:

- 30 Series 1/2 names (`1.0` through `2.4b`);
- 10 Series 3 names (`3.0` through `3.4b`); and
- 6 Series 4 names (`4.0p`, `4.0r`, `4.0f`, `4.0g`, `4.0a`, `4.0c`).

`cycle_steering_model()` moves through that tuple with wraparound and updates the active name only when `WebcamVisionProcessor.set_model_choice()` returns true.

## Current Jetson Orin Nano path

In `camera_only` mode, the Raspberry Pi 5 does not load a local checkpoint. It records the requested name, clears cached analysis, and sends the name with subsequent frames. A successful Raspberry Pi 5 selection proves only that the name was accepted; Jetson Orin Nano logs and a fresh matching response are required to prove that the ONNX artifact loaded.

For Series 4 PC/PCF models, Jetson Orin Nano resets causal steering history on load or switch so commands from the previous model do not enter the new model's input history.

## Local Raspberry Pi 5 path

When local PyTorch inference is enabled, `_load_steering_model()` builds and loads the requested Series 1/2 checkpoint before taking the model lock. If loading fails, the method returns false and retains the previous model. After a successful swap, cached analysis and timestamps are cleared.

The lock ordering avoids intentionally exposing a partially assigned model/reference pair to the camera worker. It is a concurrency design, not a formal guarantee against every process or hardware fault.

## Verification

- Confirm the dashboard reports the intended name.
- For local models, confirm the successful-load log and fresh inference.
- For Series 3/4, confirm Jetson Orin Nano logs the matching ONNX path/provider and the Raspberry Pi 5 receives fresh results for that exact model name.
- Keep autonomy off during the switch and initial verification.

## Related pages

- [Model Choices](model-choices.md)
- [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md)
- [Model Steering Bench Test](../../testing/bench-tests/model-steering.md)
