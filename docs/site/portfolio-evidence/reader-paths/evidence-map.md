# Evidence Map

This page maps public claims to the strongest available proof and states what is still missing.

| Claim | Best evidence | What it proves | Limitation or open item |
|---|---|---|---|
| A physical car is controlled by the software | Runtime source, systemd services, YouTube demonstrations | The project operates real camera, steering, motors, sensors, and display hardware | A video alone does not prove every safety state |
| v3.4 is the current field-selected model | July 13 operator comparison, Series 3 table, v3.4 card | v3.4 beat v3.4b/v3.3/v3.3b on the tested car and shadow cases | Route, weather, takeovers, and clip IDs were not recorded |
| Models are evaluated beyond MAE | `docs/steering_model_report.pdf`, Series 3 table, evaluator source | Balanced nine-class, turn, median, signed-error, and confusion behavior are measured | Series 1/2 use their compatible dataset and cannot be compared as one identical contract |
| Training data is real and published | Hugging Face dataset repositories and label metadata | Frames and labels exist outside the local workstation | Public metadata should be checked against each card's exact snapshot |
| The runtime remains responsive with Jetson off | Async-client tests, runtime code, July 14 hardware retest | Powered-off inference no longer blocks manual steering | No long-duration latency trace has been published yet |
| LiDAR can slow and stop without steering | LiDAR policy source and automated tests | Center-only decisions are deterministic in software | Latest behavior still needs a preserved physical pass/fail test |
| Dashboard uses a recoverable dedicated link | USB installer, keeper service, receiver/sender source | Fixed-address USB telemetry and service recovery are implemented | Damaged cables or ports can still prevent physical enumeration |
| Safety limits are explicit | Safety-case and ethics pages | The project does not claim public-road or unattended readiness | These are project controls, not third-party certification |

## Direct Artifact Index

| Artifact | Location |
|---|---|
| Production controller | `code/controller/current/rc_car.py` |
| Control loop and arbitration | `code/controller/current/rc_car_app/runtime.py` |
| Jetson inference server | `code/controller/current/jon_server.py` |
| Model loading and decoding | `code/controller/current/rc_car_app/vision.py` |
| LiDAR decision logic | `code/controller/current/rc_car_app/lidar_avoidance.py` |
| Dashboard receiver | `code/controller/current/z2w_dashboard.py` |
| Series 3 trainer | `code/ai_models_datasets/series_3/sidewalkpilot_trainer.py` |
| Cross-model evaluator | `code/test_files/evaluate_sidewalkpilot_models.py` |
| Evaluation PDF | `docs/steering_model_report.pdf` |
| Model repositories | [Hugging Face profile](https://huggingface.co/ram-shreyas-naik-sabavat) |
| Training dashboard | [Weights & Biases](https://wandb.ai/Sidewalk-Pilot/SidewalkPilot/table?nw=nwusersidewalkpilot) |

## Evidence Collection Standard

A complete future field record should include:

- date and local time;
- model version and exact artifact hash;
- route or route segment identifier;
- lighting and weather;
- AEB state and relevant calibration;
- autonomous distance or duration;
- manual takeover count and reasons;
- linked video/log/CSV filenames;
- pass/fail decision and next action.

This standard is intentionally stricter than the existing July 13 record. It converts a strong operator observation into evidence another reviewer can audit.
