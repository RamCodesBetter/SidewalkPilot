# Evidence Map

This page maps important SidewalkPilot claims to the strongest available proof and states what the proof does not establish.

| Claim | Best evidence | What it proves | Limitation or open item |
|---|---|---|---|
| The software controls a physical car | Runtime source, systemd units, field videos, hardware photos | Camera, controller, steering, motors, sensors, and dashboard have operated together | A demonstration does not prove safe behavior in every environment |
| v3.4 is the current field-selected model | July 13 comparison, Series 3 table, v3.4 model card | v3.4 beat v3.4b/v3.3/v3.3b in the tested shadow and turn cases | Route, weather, clips, and takeover counts were not preserved |
| Six Series 4 models were trained | Three trainers, W&B runs, local ONNX artifacts, model signatures | PC, CF, and PCF each produced final and best-validation artifacts | None has passed physical field testing or public release review |
| All model families were compared on later data | `docs/steering_model_report.pdf`, evaluation JSON, evaluator source | 46 checkpoints were decoded correctly and scored on one frozen 6,952-frame S3/4 subset | Offline labels cannot measure road-edge risk, oscillation, or recovery behavior |
| Training data is real and published | Hugging Face dataset repositories and label metadata | The Series 3/4 real dataset contains 81,237 labeled images | Public metadata should be checked against the exact snapshot used for a run |
| Manual control remains responsive when Jetson Orin Nano is off | Background inference-client code, automated tests, July 14 hardware retest | Powered-off inference no longer blocks the Raspberry Pi 5 control loop | A long-duration latency trace is not yet published |
| LiDAR can slow and stop without steering | LiDAR policy source, automated tests, dashboard state | Center-corridor decisions are deterministic in software | The latest configuration still needs a preserved physical pass/fail record |
| The dashboard uses a dedicated recoverable link | USB installer, keeper service, sender/receiver source | Fixed-address USB telemetry and link recovery are implemented | A damaged cable or port can still prevent USB enumeration |
| Route planning is implemented | Navigation source, graph, and CLI utilities | A* can build typed sidewalk/manual route segments and prepare crosswalk handoffs | An indexed end-to-end GPS field result is not preserved |
| The physical interfaces are implemented | Hardware source, bench utilities, wiring records, and field operation | Camera, LiDAR, GPS, servo, motors, controller, and dashboard have working software interfaces | Configuration alone does not prove reliability, water resistance, EMI immunity, or stopping distance |
| Safety limits are explicit | Safety-case and ethics pages | The project does not claim public-road, unattended, or certified operation | These controls are project rules, not third-party certification |

## Bounded Project Claims

### Autonomy

SidewalkPilot has demonstrated supervised camera-based steering on a physical RC car. The Jetson Orin Nano proposes steering from the newest camera frame; the Raspberry Pi 5 accepts only fresh results, applies control and enabled safety policy, and remains the final actuator authority. The operator can brake, take over, or shut down the run. This is not a claim of SAE automation, unattended operation, public-road readiness, or safe operation around arbitrary pedestrians.

### Data and Models

The published Series 1/2 correction set contains 2,224 labeled real images across 13 sources. Series 3/4 share 81,237 labeled real images. CARLA frames are published separately and must already exist on disk; the trainers do not start the simulator. Steering labels retain the logical 0-to-180 target, while hardware trim remains a runtime concern.

The July 13 field comparison selected v3.4 over v3.4b, v3.3, and v3.3b in the tested shadow and turn cases. Series 4 PC and PCF lead v3.4 on several common offline metrics, but none has a physical-car verdict. Offline ranking selects candidates; it does not promote a model by itself.

### Safety and Navigation

With AEB enabled, LiDAR can reduce forward throttle or request a hard brake from center-corridor distance. It does not classify obstacles or choose steering. The current thresholds and software tests do not establish physical stopping distance under every payload or surface.

Navigation code can plan over the mapped sidewalk graph, penalize turns and crossings, split routes into automatic sidewalk and manual crossing segments, and prepare a handoff before a crossing. GPS-driven end-to-end segment switching has not been preserved as a quantitative field result, and arbitrary-address routing remains out of scope.

### Hardware and Reproducibility

The current assembly uses the Jetson Orin Nano for inference, Raspberry Pi 5 for sensors and final control, and Zero 2 W for display. Reproducing a software result requires the exact code revision, dataset revision, split, command, seed, environment, and artifact hash. Reproducing a field result additionally requires equivalent hardware, wiring, calibration, power state, route, conditions, logs, video, and takeover records.

## Demonstration Status

| Demonstration | Current evidence | Honest status |
|---|---|---|
| Integrated autonomous run | Supervised physical runs and public project videos | Demonstrated, but no single indexed hero clip is paired here with its complete log and metadata |
| v3.4 shadow comparison | July 13 operator comparison | Strongest current field result; route, weather, clip IDs, and takeover count were not preserved |
| LiDAR slowdown and hard brake | Policy source and automated tests | Implemented in software; latest physical pass/fail and stopping-distance record remains open |
| Navigation and crosswalk handoff | A* graph, segment planner, runtime state transitions | Implemented in code; no indexed end-to-end GPS field demonstration |
| Dashboard | Physical HUB75 display, sender/receiver source, layout tests | Operational and observable; dashboard failure does not control vehicle motion |
| v3.1b night failure | Operator note describing warm-light bias and blocky steering | Historical observation only; matching clip, CSV, route, and artifact hash are not indexed |
| Series 4 | Training runs, ONNX artifacts, CUDA/runtime checks, common evaluation | Ready for controlled field comparison; no physical verdict yet |

## Direct Artifact Index

| Artifact | Location |
|---|---|
| Raspberry Pi 5 controller entrypoint | `code/controller/current/rc_car.py` |
| Control loop and arbitration | `code/controller/current/rc_car_app/runtime.py` |
| Jetson Orin Nano inference server | `code/controller/current/rc_car_app/jetson_inference_server.py` |
| Raspberry Pi 5 inference client and model selection | `code/controller/current/rc_car_app/vision.py` |
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

A physical safety demonstration should first restrain the car or unload its wheels, verify fresh sensor data, move a broad target through each configured distance boundary, and record dashboard state, CSV telemetry, requested throttle, and brake output. Low-speed motion testing should follow only after the static policy test passes.
