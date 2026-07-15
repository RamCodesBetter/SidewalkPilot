# Evidence Map

This page maps important SidewalkPilot claims to the strongest available proof and states what the proof does not establish.

| Claim | Best evidence | What it proves | Limitation or open item |
|---|---|---|---|
| The software controls a physical car | Runtime source, systemd units, field videos, hardware photos | Camera, controller, steering, motors, sensors, and dashboard have operated together | A demonstration does not prove safe behavior in every environment |
| v3.4 is the current field-selected model | July 13 comparison, Series 3 table, v3.4 model card | v3.4 beat v3.4b/v3.3/v3.3b in the tested shadow and turn cases | Route, weather, clips, and takeover counts were not preserved |
| Six Series 4 models were trained | Three trainers, W&B runs, local ONNX artifacts, model signatures | PC, CF, and PCF each produced final and best-validation artifacts | None has passed physical field testing or public release review |
| All model families were compared on later data | `docs/steering_model_report.pdf`, evaluation JSON, evaluator source | 46 checkpoints were decoded correctly and scored on one frozen 6,952-frame S3/4 subset | Offline labels cannot measure road-edge risk, oscillation, or recovery behavior |
| Training data is real and published | Hugging Face dataset repositories and label metadata | The Series 3/4 real dataset contains 81,237 labeled images | Public metadata should be checked against the exact snapshot used for a run |
| Manual control remains responsive when Jetson is off | Background inference-client code, automated tests, July 14 hardware retest | Powered-off inference no longer blocks the Pi control loop | A long-duration latency trace is not yet published |
| LiDAR can slow and stop without steering | LiDAR policy source, automated tests, dashboard state | Center-corridor decisions are deterministic in software | The latest configuration still needs a preserved physical pass/fail record |
| The dashboard uses a dedicated recoverable link | USB installer, keeper service, sender/receiver source | Fixed-address USB telemetry and link recovery are implemented | A damaged cable or port can still prevent USB enumeration |
| Safety limits are explicit | Safety-case and ethics pages | The project does not claim public-road, unattended, or certified operation | These controls are project rules, not third-party certification |

## Direct Artifact Index

| Artifact | Location |
|---|---|
| Pi controller entrypoint | `code/controller/current/rc_car.py` |
| Control loop and arbitration | `code/controller/current/rc_car_app/runtime.py` |
| Jetson inference server | `code/controller/current/rc_car_app/jetson_inference_server.py` |
| Pi inference client and model selection | `code/controller/current/rc_car_app/vision.py` |
| LiDAR decision logic | `code/controller/current/rc_car_app/lidar_avoidance.py` |
| Dashboard receiver | `code/controller/current/z2w_dashboard.py` |
| Series 1/2 trainer | `code/ai_models_datasets/series_1_and_2/sidewalkpilot_trainer.py` |
| Series 3 trainer | `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py` |
| Series 4 PC trainer | `code/ai_models_datasets/series_3_and_4/series_4_0pr_sidewalkpilot_trainer.py` |
| Series 4 CF trainer | `code/ai_models_datasets/series_3_and_4/series_4_0fg_sidewalkpilot_trainer.py` |
| Series 4 PCF trainer | `code/ai_models_datasets/series_3_and_4/series_4_0ac_sidewalkpilot_trainer.py` |
| Cross-model evaluator | `code/test_files/models/evaluate_sidewalkpilot_models.py` |
| Evaluation JSON | `docs/steering_eval_current_labels.json` |
| Evaluation PDF | `docs/steering_model_report.pdf` |
| Public artifacts | [Hugging Face profile](https://huggingface.co/ram-shreyas-naik-sabavat) |
| Training runs | [Weights & Biases](https://wandb.ai/Sidewalk-Pilot/SidewalkPilot/table?nw=nwusersidewalkpilot) |

## Evidence Collection Standard

A complete future field record should include:

- Date and local time;
- Model version and exact artifact SHA-256;
- Route or route-segment identifier;
- Lighting and weather;
- AEB state and relevant calibration;
- Autonomous distance or duration;
- Manual takeover count and reason for each takeover;
- Video, log, and CSV filenames;
- Pass/fail decision and next action.

This standard is intentionally stricter than the July 13 record. It turns an operator observation into evidence another reviewer can audit.
