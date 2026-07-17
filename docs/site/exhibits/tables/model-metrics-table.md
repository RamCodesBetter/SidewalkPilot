# Evidence Tables

The canonical generated comparison is [steering_model_report.pdf](../../steering_model_report.pdf). It contains all 46 checkpoints, class-balanced gradient tables, confusion matrices, and per-model details. This page explains the compact metrics used to read it.

## Model Families

| Family | Models | Input | Output | Parameters |
|---|---:|---|---|---:|
| Series 1 | 20 | 200x66 image | direct steering | 672,877 |
| Series 2 | 10 | 200x66 image | direct steering | 672,877 |
| Series 3 | 10 | 320x180 image | v3.0 regression; v3.1+ 19-value hybrid | approximately 5.53M |
| Series 4 PC | 2 | image + three prior targets | one 18-value horizon | 5,569,186 |
| Series 4 CF | 2 | image | four 18-value horizons | 5,537,560 |
| Series 4 PCF | 2 | image + three prior targets | four 18-value horizons | 5,572,696 |

## Common Challenge Set

All 46 models are scored on the same frozen 6,952-frame subset from the Series 3/4 dataset. The evaluator applies the matching resize, model invocation, and decoder for each architecture. This reveals how early models behave on the later shadow/lighting distribution instead of comparing unrelated per-series test sets.

## Primary Metrics

| Metric | Calculation | What it reveals |
|---|---|---|
| Bal9 | mean recall of the nine steering classes | class-balanced exact steering capability |
| Turn exact | exact-class recall across every non-ST target frame | whether the model commits to the correct turn class |
| Turn +/-1 | non-ST recall allowing one adjacent class | whether turn direction/magnitude is approximately correct |
| ST exact | recall for the 85-95 degree straight class | straight preservation |
| MAE | mean absolute steering error in degrees | average numeric error, sensitive to outliers and class imbalance |
| Median | median absolute steering error | typical numeric error |
| Signed | mean prediction minus target | systematic right-positive or left-negative bias |
| Hold-last MAE | error from repeating the previous target | whether the learned model beats a temporal persistence baseline |

No single column is the field verdict. Bal9 and turn metrics prevent straight-heavy data from hiding turn collapse; MAE/median expose numeric precision; signed error exposes bias; field testing exposes behavior absent from labels.

## Current Baseline and Series 4

| Model | Bal9 | Turn exact | Turn +/-1 | ST exact | MAE | Median | Signed |
|---|---:|---:|---:|---:|---:|---:|---:|
| v3.4 | 24.2% | 22.6% | 56.2% | 64.2% | 15.083 | 6.069 | +0.418 |
| v3.4b | 22.4% | 19.1% | 51.2% | 72.7% | 13.985 | 2.478 | -1.566 |
| v4.0p | **34.5%** | **32.1%** | **65.9%** | 67.7% | 12.396 | 2.967 | +0.120 |
| v4.0r | 32.9% | 27.4% | 62.6% | **77.6%** | 11.636 | 1.846 | -1.136 |
| v4.0f | 25.4% | 23.5% | 56.4% | 62.8% | 15.623 | 6.723 | +1.057 |
| v4.0g | 20.4% | 17.1% | 46.4% | 76.0% | 14.116 | 2.114 | -1.864 |
| v4.0a | 33.5% | 30.9% | 65.3% | 68.1% | 12.379 | 3.115 | +0.290 |
| v4.0c | 32.0% | 29.4% | 62.9% | 75.5% | **11.321** | **1.825** | -0.981 |

The table makes the tradeoff visible. v4.0p leads balanced and turn metrics; v4.0c leads raw error; v4.0r has the highest straight recall. Those differences justify a physical comparison rather than declaring a winner from one column.

## Field Status

| Version | Field evidence |
|---|---|
| v3.4 | Current selection; handled every presented shadow case and tested ordinary turns on July 13, 2026 |
| v3.4b | Tested in the same comparison; slightly worse than v3.4 |
| v3.3 | Tested; worse than v3.2 |
| v3.3b | Tested; much worse than v3.2b |
| v4.0p/r/f/g/a/c | Not yet field-tested |

The July 13 result is qualitative because exact route, conditions, clips, and takeover counts were not preserved.

## Dataset Summary

| Dataset | Published size/status | Main use |
|---|---:|---|
| Series 1/2 field set | 2,224 labeled images | Historical direct-regression training/evaluation |
| CARLA set | 50,000 generated images used in early work | Synthetic assistance for Series 1/2 history |
| Series 3/4 set | 81,237 real images | Current Series 3 and experimental Series 4 training |
| Common challenge subset | 6,952 anchors | Cross-generation offline comparison |

## Evidence Matrix

| Claim area | Strongest artifact | Remaining gap |
|---|---|---|
| Model architecture | Trainers, ONNX contracts, parameter counts | Independent reproduction |
| Offline capability | Evaluator JSON/PDF and confusion matrices | Distribution/field transfer |
| v3.4 field selection | July 13 operator comparison | Complete route, clips, and takeover record |
| Series 4 | Training runs, artifacts, evaluator, runtime smoke tests | Physical field comparison |
| LiDAR AEB | Source and deterministic tests | Preserved stopping-distance/false-trigger field test |
| Hardware | Wiring/config, photos, bench utilities | Finished matching PCB revision |

Hardware BOM, failure details, and test procedures are maintained in [Build Overview](../../hardware/build-overview.md), [Failure Records](../../testing/failures/overview.md), and [Field Testing](../../testing/field-testing/overview.md) instead of duplicated tables here.

See [Bal9](../../model-evaluation/offline-evaluation/bal9.md), [Model Selection Rubric](../../model-evaluation/comparisons/model-selection-rubric.md), and [Series 4 Models](../../ai-and-models/model-zoo/series-4.md).
