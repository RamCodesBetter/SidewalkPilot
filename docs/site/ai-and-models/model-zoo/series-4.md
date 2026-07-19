# Series 4 Models

Series 4 keeps the Series 3 visual backbone and hybrid steering decoder while testing whether nearby steering targets improve the current prediction. It removes learned throttle and separates three contracts: previous-context (PC), current-plus-future supervision (CF), and both together (PCF).

## Version Map

| Generation | Pair | Final epoch | Validation-selected | Runtime input | Training target |
|---|---|---|---|---|---|
| 4.0 | <code class="nowrap">PC</code> | `4.0p` | `4.0r` | image + previous 3 steering targets | current target |
| 4.0 | <code class="nowrap">CF</code> | `4.0f` | `4.0g` | image | current + next 3 targets |
| 4.0 | <code class="nowrap">PCF</code> | `4.0a` | `4.0c` | image + previous 3 steering targets | current + next 3 targets |
| 4.1 | <code class="nowrap">PC</code> | `4.1p` | `4.1r` | image + previous 3 steering targets | current target |
| 4.1 | <code class="nowrap">CF</code> | `4.1f` | `4.1g` | image | current + next 3 targets |
| 4.1 | <code class="nowrap">PCF</code> | `4.1a` | `4.1c` | image + previous 3 steering targets | current + next 3 targets |

Future steering values are labels used during training. They are never runtime inputs. PC emits `[batch,1,18]`; CF and PCF emit `[batch,4,18]`. Each 18-value horizon contains nine steering-class logits and nine class-local offsets. Live control uses horizon 0.

## 4.0 Common Evaluation

These values come from the frozen 6,952-frame challenge set used by the common evaluator.

| Model | Bal9 | Turn exact | Turn +/-1 | ST exact | MAE | Median | Signed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `4.0p` | **34.5%** | **32.1%** | **65.9%** | 67.7% | 12.396 | 2.967 | +0.120 |
| `4.0r` | 32.9% | 27.4% | 62.6% | **77.6%** | 11.636 | 1.846 | -1.136 |
| `4.0f` | 25.4% | 23.5% | 56.4% | 62.8% | 15.623 | 6.723 | +1.057 |
| `4.0g` | 20.4% | 17.1% | 46.4% | 76.0% | 14.116 | 2.114 | -1.864 |
| `4.0a` | 33.5% | 30.9% | 65.3% | 68.1% | 12.379 | 3.115 | +0.290 |
| `4.0c` | 32.0% | 29.4% | 62.9% | 75.5% | **11.321** | **1.825** | -0.981 |

The offline table made PC and PCF look strongest. Physical testing contradicted that simple ranking.

Public v4.0 model repositories: [v4.0p](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v4.0p), [v4.0r](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v4.0r), [v4.0f](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v4.0f), [v4.0g](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v4.0g), [v4.0a](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v4.0a), and [v4.0c](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v4.0c).

## 4.0 Field Result

All six 4.0 checkpoints were compared on the physical car under supervision:

- `4.0f` was the only viable 4.0 candidate. It and v3.4 produced complementary results: each passed two cases that the other failed. That comparison did not establish one as generally better.
- `4.0g` was worse than `4.0f`.
- `4.0p`, `4.0r`, `4.0a`, and `4.0c` repeatedly echoed a previous steering prediction. After a large prediction, later outputs could remain near that turn instead of following the new image. They were not drivable enough for promotion.
- Within the failed history pairs, `4.0p` was better than `4.0r`, and `4.0a` was slightly better than `4.0c`.

This is why v3.4 remains the default even though several 4.0 checkpoints score better offline. The comparison was supervised and video was captured, but it was not a formal route-controlled benchmark with a preserved per-case score sheet.

## 4.1 Correction Experiments

The 4.1 runs were created after reviewing the 4.0 failure clips. They keep the same PC, CF, and PCF questions while changing the training behavior that could reward steering echo.

| Run | Change | Final | Validation-selected model |
|---|---|---|---|
| `4.1pr` | encode bounded steering motion instead of unrestricted absolute-history fusion; add history corruption, counterfactual-history loss, and closed-loop selection | `4.1p` | `4.1r`, epoch 1 |
| `4.1fg` | emphasize the current horizon and add trajectory-delta consistency across future horizons | `4.1f` | `4.1g`, epoch 15 |
| `4.1ac` | combine robust history handling with future-trajectory supervision | `4.1a` | `4.1c`, epoch 10 |

All three 4.1 runs completed 25 epochs and exported six ONNX models. They are not yet supported by the live model selector and have not been tested on the car. Their purpose is to test whether the 4.0 history failure can be corrected without collecting a new dataset.

## 4.1 Common Evaluation

| Model | Bal9 | Turn exact | Turn +/-1 | ST exact | MAE | Median | Signed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `4.1p` | 25.1% | 23.1% | 56.5% | 65.7% | 14.585 | 5.048 | -0.144 |
| `4.1r` | 17.8% | 9.2% | 37.2% | 87.5% | **13.382** | **1.431** | -5.765 |
| `4.1f` | 25.1% | 22.9% | **57.9%** | 61.5% | 15.466 | 7.218 | +1.183 |
| `4.1g` | 24.0% | 21.2% | 56.8% | 67.4% | 14.652 | 4.659 | +0.555 |
| `4.1a` | **25.3%** | 22.9% | 57.0% | 63.2% | 14.805 | 6.352 | +0.130 |
| `4.1c` | 23.2% | 19.5% | 52.3% | 75.0% | 13.566 | 2.270 | -0.984 |

The 4.1 open-loop results do not beat the strongest 4.0 PC/PCF rows. That is not sufficient to reject the correction, because 4.1 was designed around the closed-loop failure those open-loop rows missed. `4.1r` also shows a familiar warning pattern: very high straight recall, weak turn recall, and low median error. It should not be selected from MAE alone.

See [Series 4 Temporal Experiments](../architecture/series-4-plan.md) for the layer and loss details, and [Model Selection Rubric](../../model-evaluation/comparisons/model-selection-rubric.md) for the promotion rules.
