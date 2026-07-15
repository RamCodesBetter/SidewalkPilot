# Training Flow Diagram

This page diagrams how a driven photo becomes a trained steering model: from labeled field captures, through the dataset and augmentation pipeline, into the network, and out to a checkpoint that either runs on the Pi (Series 1/2) or on the Jetson (Series 3/4). It is the offline counterpart to the runtime diagrams.

```text
manual drive
    |
    v
camera frame + logical steering + absolute throttle
    |
    v
dated run folder -> audit -> frozen dataset snapshot
    |
    v
family split + train-only augmentation + weighted sampling
    |
    v
PyTorch optimization -> final/best checkpoint -> ONNX export
    |
    v
common offline evaluation -> controlled physical field test -> promotion decision
```

## From Capture to Label

Photos are captured live on the Pi into dated run folders with absolute steering/throttle labels. The published Series 3/4 dataset contains 81,237 labeled real images. Capture count alone is not a quality claim; source, lighting, steering balance, and split integrity remain part of the audit.

## Dataset and augmentation

The trainers live in `code/ai_models_datasets/series_1_and_2/` and `code/ai_models_datasets/series_3_and_4/`. The Series 3 trainer (`series_3_sidewalkpilot_trainer.py`):

- Normalizes every label to servo degrees, then resizes images to **320x180** (Series 1/2 uses 200x66).
- Buckets steering to check and rebalance the distribution across left/straight/right (`SERVO_BUCKETS`, with a weighted sampler), because the dataset's known gap is turns — especially mid-right and turns-in-shadow.
- Supports shadow, color, camera-jitter, and optional label-aware horizontal-flip augmentation. The saved run command is required before attributing a specific checkpoint to a particular augmentation setting.

## Network and outputs

- **Series 1/2 - `SteeringAutonomyV2`, ~0.67M params:** a small CNN backbone with a single `tanh` regression head that outputs one steering angle (`90 + scale * tanh`). It can run directly on the Pi.
- **Series 3 — `SidewalkPilotV3`, 5,534,115 params:** a six-convolution backbone for Jon. Its hybrid head emits 9 steering-class logits, 9 class-local offsets, and 1 throttle value. The runtime selects a class and decodes its local offset into a servo angle.
- **Series 4 — PC, CF, and PCF experiments, about 5.54-5.57M params:** reuse the visual backbone and 18-value steering horizon. Previous targets are causal inputs for PC/PCF; future targets are training supervision for CF/PCF, never runtime inputs.

## Export and telemetry

Series 3 checkpoints export to ONNX for the Jetson; deploying a new version means adding it to the Pi's `STEERING_MODEL_VERSIONS` and copying the `.onnx` to Jon, which auto-resolves it. Training runs report metrics to Weights & Biases.

## Key Finding

MAE is insufficient here: a lower-MAE checkpoint can still be more straight-collapsed. Models are judged with class-balanced/turn metrics and physical behavior. The July 13 field comparison found v3.3 worse than v3.2 and v3.3b much worse than v3.2b; v3.4 became the field-selected baseline.

## What this exhibit documents

The checked-in path from operator-labeled field data through dataset construction, training, export, offline evaluation, and field selection. Reproducing a checkpoint still requires the exact dataset snapshot, command, code revision, seed, and environment.

## Evidence

- Source anchors: `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`, the three Series 4 wrappers plus `series_4_common.py`, `series_1_and_2/sidewalkpilot_trainer.py`, and `runtime.py` (`append_photo_run_row`, `finalize_photo_run`).

## Related pages

- `portfolio-evidence/claims-and-proof/reproducibility-claim.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
