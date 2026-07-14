# Steering Model Series

SidewalkPilot keeps model generations separate because they have different preprocessing, output contracts, and deployment assumptions.

| Series | Input | Prediction design | Deployment role |
|---|---|---|---|
| 1 | `200x66` image | Direct continuous steering | Original proof that camera-only sidewalk steering works |
| 2 | `200x66` image | Refined direct steering; selected versions test HSV/CLAHE preprocessing | Historical Pi-era refinement and comparison baseline |
| 3.0 | `320x180` image | Two-output steering/throttle regression | First heavy Jetson-only Series 3 design |
| 3.1-3.4 | `320x180` image | 19 raw outputs: 9 class logits, 9 within-class offsets, 1 throttle | Current hybrid Jetson architecture |
| 4 | Not frozen | Parallel architecture research | Planning only; no model or runtime selection yet |

## Current Production Choice

Regular **v3.4** is the field-selected default as of July 13, 2026. The controller keeps every earlier model selectable for comparison, but `DEFAULT_STEERING_MODEL_CHOICE` in `code/controller/current/rc_car_app/vision.py` explicitly names `3.4`; list order no longer chooses the default.

The field comparison found v3.4 strongest across the tested shadows and normal turns. v3.4b was slightly worse. v3.3 and v3.3b were regressions relative to their v3.2 counterparts. See [Shadow Robustness](../../model-evaluation/field-evaluation/shadow-robustness.md).

## Runtime Contract

The Pi captures `1280x720` BGR frames and sends them with the selected model version to the Jetson. The Jetson inference server resolves `SidewalkPilot-v<version>.onnx` before `.pt` or `.pth`, preprocesses according to the model family, decodes the output by architecture, and returns steering plus throttle telemetry. The Pi currently uses model steering while LiDAR owns only center-corridor throttle limiting and emergency braking.

Source files:

- `code/controller/current/rc_car_app/vision.py`: model list and production default.
- `code/controller/current/rc_car_app/jetson_client.py`: frame/version request.
- `code/controller/current/rc_car_app/jetson_inference_server.py`: model resolution, preprocessing, decode, and inference.
- `code/ai_models_datasets/series_3/sidewalkpilot_trainer.py`: Series 3 architecture and training.
- `code/ai_models_datasets/series_4/SERIES4_PLAN.md`: Series 4 experiment contract.

## Validation Rule

Offline error cannot select a production model by itself. The dataset is straight-heavy, so a model can improve aggregate MAE by predicting near-center too often while losing turns. Promotion requires turn-class behavior, signed error, shadow testing, normal left/right turns, command freshness, and manual-takeover review.
