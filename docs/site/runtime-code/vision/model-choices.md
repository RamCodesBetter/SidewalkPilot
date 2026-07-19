# Model Choices

The live runtime can select 46 checkpoints from Series 1 through Series 4.0. The offline report contains 52 models because it also evaluates six Series 4.1 checkpoints that are not yet registered. The live registry is `STEERING_MODEL_VERSIONS` in `code/controller/current/rc_car_app/vision.py`.

## Registry

| Family | Choices |
|---|---|
| Series 1 | `1.0`, `1.0b` through `1.9`, `1.9b` |
| Series 2 | `2.0`, `2.0b` through `2.4`, `2.4b` |
| Series 3 | `3.0`, `3.0b` through `3.4`, `3.4b` |
| Series 4 PC | `4.0p`, `4.0r` |
| Series 4 CF | `4.0f`, `4.0g` |
| Series 4 PCF | `4.0a`, `4.0c` |

`DEFAULT_STEERING_MODEL_CHOICE` is `3.4`. The environment variable `RC_CAR_STEERING_MODEL` can override startup selection.

The current `rc_car.py` intentionally has no `--model` flag. Run `car`, then use the dashboard model page and D-pad controls to cycle the tuple. This keeps field selection visible on the car instead of hidden in a shell command.

## Raspberry Pi 5 and Jetson Orin Nano Responsibilities

When `JETSON_STEERING_HOST` is configured, the Raspberry Pi 5 camera runs in capture-only mode. Selecting a model updates the version string attached to each JPEG request. Jetson Orin Nano hot-swaps to `SidewalkPilot-v<version>.onnx` when available, preferring ONNX over TorchScript/PTH.

The Raspberry Pi 5 does not load a heavy model in this mode. It keeps the active name, captures frames, receives decoded steering, rejects stale results, and applies smoothing/safety/hardware mapping.

## Series 4

Jetson Orin Nano inspects ONNX metadata instead of hard-coding six filenames:

- One image input and `[batch,4,18]` output -> CF;
- Image plus `target_history[batch,3]` and `[batch,1,18]` -> PC;
- Image plus history and `[batch,4,18]` -> PCF.

Only the current horizon commands the car. At autonomy start, PC/PCF history is seeded from the latest three manual steering targets and then updated once per completed inference. Switching models or reconnecting resets the prediction sequence.

## Failure Behavior

- Unknown name: rejected by the registry.
- Missing artifact on Jetson Orin Nano: model switch logs a failure and does not fabricate an output.
- Powered-off/unreachable Jetson Orin Nano: asynchronous network waits stay off the controller loop.
- Stale result: autonomy confidence drops and the runtime stops rather than replaying an old command.

See [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md) and [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md).
