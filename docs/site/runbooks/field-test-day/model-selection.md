# Model Selection

This runbook selects and verifies the steering checkpoint used for a physical test. The selected name is not enough: the correct artifact must be present on the computer that performs inference, the log must confirm the load, and the dashboard must show the intended version.

## Available Models

The registry in `code/controller/current/rc_car_app/vision.py` contains all 46 evaluated checkpoints:

| Family | Versions | Inference computer |
|---|---|---|
| Series 1 | `1.0/1.0b` through `1.9/1.9b` | Raspberry Pi 5 when local inference is used, or Jetson Orin Nano through ONNX |
| Series 2 | `2.0/2.0b` through `2.4/2.4b` | Raspberry Pi 5 when local inference is used, or Jetson Orin Nano through ONNX |
| Series 3 | `3.0/3.0b` through `3.4/3.4b` | Jetson Orin Nano |
| Series 4 PC | `4.0p`, `4.0r` | Jetson Orin Nano, image plus causal history |
| Series 4 CF | `4.0f`, `4.0g` | Jetson Orin Nano, image only |
| Series 4 PCF | `4.0a`, `4.0c` | Jetson Orin Nano, image plus causal history |

The startup default is v3.4. `RC_CAR_STEERING_MODEL` can override it before launch. The current `rc_car.py` has no `--model` option; field switching happens on the dashboard model page.

## Preconditions

1. Copy the intended `SidewalkPilot-v<version>.onnx` to Jetson Orin Nano's `code/ai_models/` directory.
2. Confirm the runtime revision containing that model name is synchronized to the Raspberry Pi 5 and Jetson Orin Nano.
3. Start the Jetson Orin Nano inference server and the Raspberry Pi 5 controller.
4. Keep AEB state, steering trim, tire pressure, battery state, and route constant across comparisons.
5. Prepare a run record with date/time, lighting, route segment, model hash, clips/logs, and takeover fields.

## Select and Confirm

1. Open the dashboard model page.
2. Use the D-pad control to cycle to the intended version.
3. Watch the Raspberry Pi 5 and Jetson Orin Nano logs for the successful model switch/load message.
4. Confirm the dashboard displays the intended full model suffix, including `p/r/f/g/a/c` for Series 4.
5. With the wheels safely unloaded or the car restrained, confirm fresh steering responses before placing it on the route.

Jetson Orin Nano inspects the ONNX signature. CF uses only the image. PC and PCF use a three-value target history that starts at `[90,90,90]`, updates from each completed model prediction, and resets after a model switch, reconnect, or manual/status period.

## Comparison Order

The common evaluator orders the first Series 4 field pass as:

1. v3.4 reference run;
2. v4.0p;
3. v4.0r;
4. v4.0a;
5. v4.0c;
6. v3.4b;
7. v4.0f;
8. v4.0g;
9. Optional v3.4 repeat to detect route or battery drift.

This order prioritizes Bal9 and turn capability while retaining lower-MAE and image-only controls. It is not a claim that v4.0p is already better on the car.

## Stop Conditions

Do not arm autonomy when:

- The intended artifact fails to load;
- Jetson Orin Nano is unreachable or results are stale;
- The displayed version does not match the planned run;
- Manual takeover, brake, steering, or AEB checks fail;
- A PC/PCF model shows unstable autoregressive behavior;
- The route contains uncontrolled pedestrians, vehicles, or other hazards.

## Promotion Record

Offline metrics decide which models deserve scarce hardware time. Promotion still requires repeatable field behavior on ordinary left/right turns and the shadow scenarios that motivated v3.4. Record takeovers and reasons rather than relying on memory.

See [Model Selection Rubric](../../model-evaluation/comparisons/model-selection-rubric.md), [Series 4 Models](../../ai-and-models/model-zoo/series-4.md), and [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md).
