# Dataset Table

This exhibit separates the historical Series 1/2 dataset, the current Series 3/4 dataset, and the independent CARLA repository. Large image folders live on Hugging Face rather than GitHub.

## Dataset Summary

| Dataset | Size | Labels | Used by | Status |
|---|---:|---|---|---|
| Series 1 and 2 | 2,224 real images, 13 sources | absolute steering | v1.0-v2.4b | finalized and published |
| Series 3 and 4 | 81,237 real images | logical `0..180` steering and absolute physical throttle capture | v3.0-v4.0c | current shared dataset, published |
| CARLA | separate pre-generated synthetic dataset | simulator-exported labels | historical/optional source | published separately |

Public repositories:

- [SidewalkPilot_v1_and_v2](https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v1_and_v2)
- [SidewalkPilot_v3_and_v4](https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v3_and_v4)
- [SidewalkPilot_carla](https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_carla)

## Label Contract

| Field | Meaning |
|---|---|
| image/path | frame identity and ordered source membership |
| steering | absolute logical servo target from 0 to 180 degrees |
| throttle | absolute physical PWM fraction from 0.0 to 1.0 |
| source/run | capture provenance used to keep sequences together |
| timestamp/order | temporal order used by split and Series 4 windows |

Series 4 learns steering only. Its previous/future targets are derived from ordered steering labels in the Series 3/4 dataset. Future targets are supervision and are not available to the live model.

## Split and Leakage Control

Consecutive frames are often nearly identical. A random image-level split could put neighboring views of the same sidewalk moment into train and validation. The Series 3/4 trainer assigns path-sorted 100-sample windows to one side of the split. This reduces adjacent leakage but does not guarantee capture-run isolation.

Series 4 temporal windows also stay inside one capture run and one split and reject gaps greater than 0.25 seconds. This prevents a sample from reaching across a run boundary or leaking a validation target into a training sequence.

## Evaluation Subset

The generated 46-model report uses a frozen 6,952-frame challenge subset from the Series 3/4 dataset. Series 1/2 checkpoints receive their correct 200x66 preprocessing and direct-output decoder; Series 3/4 receive 320x180 preprocessing and their matching hybrid decoder.

The common subset answers “how do all generations behave on the later challenge distribution?” Original historical metrics on the Series 1/2 dataset answer a different question and remain valid only for that earlier data snapshot.

## Data Claims and Limits

- The 81,237 count describes labeled real-world images in the shared v3/v4 dataset.
- The current docs do not claim that those frames cover every sidewalk, season, weather condition, or pedestrian interaction.
- CARLA data is pre-generated on disk; the checked-in trainers do not start CARLA or capture frames from a live simulator.
- Image count alone is not model quality. Steering balance, route diversity, lighting, label quality, and split integrity all matter.

See [Dataset Overview](../../data/dataset-overview.md), [Input Labels](../../ai-and-models/training-pipeline/input-labels.md), and [Validation Split](../../research-and-math/machine-learning/validation-split.md).
