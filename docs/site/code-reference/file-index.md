# File Index

This index maps current repository areas to their responsibilities. Generated data and public artifact cards are intentionally separated from source code.

| Path | Responsibility | Notes |
|---|---|---|
| `code/controller/current/` | Live Pi, Jon, and Zero 2 W software | Field runtime |
| `code/controller/current/rc_car.py` | Minimal Pi controller entrypoint | Model selection is on-device; no runtime `--model` flag |
| `code/controller/current/rc_car_app/` | Control loop, hardware, vision client, LiDAR, GPS, logging, dashboard sender | Pi-owned package |
| `code/controller/current/rc_car_app/jetson_inference_server.py` | ONNX Runtime inference server | Runs on Jon |
| `code/controller/current/z2w_dashboard.py` | HUB75 dashboard receiver/renderer | Runs on Zero 2 W |
| `code/ai_models/` | Local/Hugging Face PTH/ONNX artifacts | Binary artifacts are ignored by Git; preserve version names |
| `code/ai_models_datasets/series_1_and_2/` | Early direct-regression trainer and metadata | 200x66 family |
| `code/ai_models_datasets/series_3_and_4/` | Series 3 trainer, three Series 4 trainers, shared temporal code | 320x180 families |
| `code/test_files/evaluate_sidewalkpilot_models.py` | Common 46-model evaluator | Produces JSON/PDF report |
| `code/test_files/` | Bench, calibration, setup, and regression utilities | Not the live control loop |
| `docs/site/` | MkDocs source | Edit this tree, not generated `site/` |
| `docs/steering_model_report.pdf` | Generated comparison report | 46 checkpoints |
| `docs/steering_eval_current_labels.json` | Machine-readable report data | Same evaluation run as PDF |

Large image datasets, generated archives, model cards, and dataset cards are not tracked as ordinary GitHub source. Published artifacts live on Hugging Face.

## Runtime Starting Points

| Need | Start with |
|---|---|
| Control ownership and arbitration | `rc_car_app/runtime.py` |
| Pins, thresholds, calibration | `rc_car_app/config.py` |
| GPIO/PWM/PCA9685 writes | `rc_car_app/hardware.py` |
| Model registry and Pi inference client | `rc_car_app/vision.py` |
| ONNX loading/decoding | `rc_car_app/jetson_inference_server.py` |
| LiDAR packet parsing | `rc_car_app/lidar.py` |
| LiDAR slowdown/brake policy | `rc_car_app/lidar_avoidance.py` |
| GPS and graph routing | `rc_car_app/navigation.py` |
| Dashboard telemetry | `rc_car_app/hub75_dashboard.py`, `z2w_dashboard.py` |

## Verification

```bash
python3 -m py_compile code/controller/current/rc_car.py code/controller/current/z2w_dashboard.py
python3 -m compileall code/controller/current/rc_car_app
```

See [Runtime Modules](runtime-modules.md), [Training Modules](training-modules.md), and [Test Files](test-files.md).
