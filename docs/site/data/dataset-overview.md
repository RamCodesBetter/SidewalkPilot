# Dataset Overview

SidewalkPilot learns from camera frames paired with the physical command that should accompany each frame. Dataset organization changed as the model architecture changed, so the project keeps the early Series 1/2 dataset separate from the larger Series 3/4 dataset.

## Published Datasets

| Dataset | Local path | Contents | Public repository |
|---|---|---|---|
| Series 1 and 2 | `code/ai_models_datasets/series_1_and_2/` | 2,224 labeled field images across 13 sources | [`SidewalkPilot_v1_and_v2`](https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v1_and_v2) |
| Series 3 and 4 | `code/ai_models_datasets/series_3_and_4/` | 81,237 labeled real-world images | [`SidewalkPilot_v3_and_v4`](https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v3_and_v4) |
| CARLA | separate synthetic dataset | Pre-generated simulation frames and labels | [`SidewalkPilot_carla`](https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_carla) |

The trainers consume files already on disk. They do not connect to a running CARLA simulator or capture simulation frames themselves. Any new CARLA collection requires a separate capture/export step before training.

## Label Meaning

Steering uses the absolute logical servo convention:

| Value | Meaning |
|---:|---|
| 0 | hard left |
| 90 | center/straight |
| 180 | hard right |

The stored steering label remains absolute even when the hardware mapping applies center trim or other calibration. This separation prevents a mechanical correction from silently redefining old training labels.

Throttle is stored as an absolute physical PWM fraction from `0.0` to `1.0`; `0.55` means 55% physical PWM. The LiDAR governor and dashboard use a separate reference scale, but manual trigger commands and saved labels do not. Series 3 can include throttle in its loss, while Series 4 deliberately removes throttle prediction and learns steering only. LiDAR and runtime policy remain responsible for slowing and stopping.

## Series 1 and 2 Dataset

The early dataset contains 2,224 JPG images and 2,224 label records across 13 field sources. The trainer resizes mixed capture resolutions to a 200x66 model input and learns direct steering regression. Corrections can override an original label without replacing the image.

This dataset is historically important because it established the complete collection, training, deployment, and field-test loop. It is not representative of the later 81,237-image lighting and shadow distribution.

## Series 3 and 4 Dataset

Series 3 and Series 4 use the same 81,237 real-world images. The three Series 4 experiments use the same dataset and split construction, making PC, CF, and PCF architecture comparisons instead of data comparisons.

The dataset includes shadow and turn cases collected after earlier field failures. Adjacent frames are highly correlated, so the Series 3/4 trainer sorts by path and assigns contiguous 100-sample windows to one side of the split. This reduces adjacent-frame leakage, but it is not a capture-run-group split and does not prove complete independence between train and validation.

Series 4 derives temporal target sequences from the ordered labels:

- PC uses the image and three previous targets to predict the current target;
- CF uses the image to predict current plus three future targets;
- PCF uses three previous targets as inputs and current plus three future targets as supervision.

Future targets are training labels only. They are never supplied to the deployed model.

## Corrections and Provenance

The Series 3 trainer can merge base `labels.json` data with optional reviewed correction records. When a correction identifies the same image as a base label, the correction wins. The current Series 4 temporal engine uses the base labels directly and has no correction-file argument. Ordered, run-prefixed filenames support temporal construction and help audit capture batches; release metadata should preserve any additional provenance.

Large image folders, dataset cards, and generated archives are intentionally not tracked in GitHub. GitHub carries source code and documentation; Hugging Face carries the published model/dataset artifacts.

Optional Series 3 correction files can be a list of sample objects, a `samples` object, or
an image-to-label mapping. A matching correction overrides the base row and can carry a
repeat factor, so every correction experiment must preserve the file and hash, command,
resolved counts, and sampler configuration. Corrections always describe the desired
logical steering target; they never encode hardware trim. The current Series 4 temporal
trainers use the ordered base labels directly.

Manual capture folders remain source evidence until review and promotion. They contain timestamped JPEGs, run-level CSV/JSON labels, and the original ordering needed by temporal models. A dataset snapshot should reference the source runs rather than silently flattening or renaming them without a mapping.

## Evaluation Use

Architecture compatibility and evaluation distribution are different questions. Series 1/2 require their 200x66 preprocessing and single-output decoder, while Series 3/4 require 320x180 preprocessing and hybrid decoders. The common evaluator adapts each model correctly, then scores all 46 checkpoints on the same frozen 6,952-frame Series 3/4 challenge subset.

That common challenge set exposes the weakness of early models on later lighting and shadow conditions. It does not erase the original Series 1/2 historical results, which remain results on their earlier dataset.

## Related Pages

- [Training Pipeline](../ai-and-models/training-pipeline/overview.md)
- [Training Split and Sampling](../research-and-math/algorithms/weighted-sampling.md)
- [Series 4 Temporal Experiments](../ai-and-models/architecture/series-4-plan.md)
- [Offline Evaluation](../model-evaluation/offline-evaluation/overview.md)
