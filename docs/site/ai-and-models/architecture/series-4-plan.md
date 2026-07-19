# Series 4 Temporal Experiments

Series 4 asks whether steering targets from nearby moments add useful information beyond one camera frame. It is a parallel research track built from the v3.4 visual backbone, not a replacement declared in advance.

## Experimental Question

The existing capture stream pairs an image at time `t` with the operator's target steering command `s_t`. Series 4 compares three ways to use that sequence:

| Name | Contract | Runtime input | Training supervision |
|---|---|---|---|
| PC | past + current | image `I_t` and `[s_{t-3}, s_{t-2}, s_{t-1}]` | `s_t` |
| CF | current + future | image `I_t` only | `[s_t, s_{t+1}, s_{t+2}, s_{t+3}]` |
| PCF | past + current + future | image `I_t` and `[s_{t-3}, s_{t-2}, s_{t-1}]` | `[s_t, s_{t+1}, s_{t+2}, s_{t+3}]` |

“Future” is supervision, not a future input. At deployment the car never receives labels from the future. CF and PCF use future targets only to shape a visual representation that must explain the direction the operator takes over the next samples.

## Controlled Design

All three runs used:

- The same 81,237-image real Series 3/4 dataset;
- The same frozen base split derived from contiguous 100-sample windows before temporal-window filtering;
- 320x180 normalized OpenCV BGR images;
- The same six-layer Series 3 convolutional backbone;
- The same nine steering buckets and within-bucket offset representation;
- 25 epochs, batch size 256, and 50,000 sampler draws per epoch;
- The same shadow augmentation and deterministic left and right balancing policy;
- Three previous targets and, where applicable, three future targets.

Temporal windows never cross a capture run, a train/validation boundary, or a timestamp gap greater than 0.25 seconds. The existing labeled captures are approximately 10 Hz, so three steps mean roughly 0.3 seconds of context, not three 30 FPS camera frames.

## Architecture

The visual backbone produces 160 feature maps. Adaptive pooling to `6x10`, flattening, and two dense layers produce a 256-value image feature.

For v4.0 PC and PCF, the three steering targets are normalized as `(s - 90) / 90`, then encoded by `3 -> 32 -> 64` dense layers. The 256 image features and 64 history features are concatenated into 320 values and fused through `320 -> 128 -> 64`.

CF has no history branch. Its image feature goes through `256 -> 64`.

Each horizon has its own `64 -> 18` head:

- Values 0-8: logits for `HL, L, L+, SL, ST, SR, R, R+, HR`;
- Values 9-17: one raw local offset for each class;
- Decoded steering: lower bucket edge plus `sigmoid(selected_offset) * bucket_width`.

PC emits shape `[batch, 1, 18]`. CF and PCF emit `[batch, 4, 18]`. Only horizon 0 commands live steering. The later CF/PCF horizons are training targets approximately 0.1, 0.2, and 0.3 seconds ahead. Averaging them into the live command could steer early or mix targets from different moments, so horizon fusion is not part of these experiments. The existing steering filter already smooths the selected horizon-0 command. Series 4 intentionally removes learned throttle.

## v4.1 Corrections

The v4.0 physical test exposed a closed-loop failure that offline metrics did not predict. The PC and PCF models often copied their recent predictions: after one large steering command, subsequent predictions stayed near that value instead of returning to the image evidence. The v4.1 trainers retain the same PC, CF, and PCF input/output contracts while changing the training objective:

- PC/PCF encode steering motion relative to the latest history value and predict a bounded correction rather than treating the history vector as an unrestricted shortcut;
- History noise, dropout, random-walk perturbations, counterfactual-history loss, and history-consistency loss discourage copying one exact training sequence;
- CF/PCF use current-dominant horizon weighting and a trajectory-delta loss so later horizons support the current decision instead of dominating it;
- Checkpoint selection includes closed-loop replay criteria in addition to ordinary validation metrics.

These changes are hypotheses encoded in the trainers. The six v4.1 models are trained and evaluated offline, but they are not in the live model selector and have not been driven.

## Size

| Contract | Parameters | FP32 ONNX size | Why it differs |
|---|---:|---:|---|
| Series 3 v3.4 | 5,534,115 | 22,136,200 bytes | visual backbone + 19-value head |
| v4.0 PC (`4.0p/r`) | 5,569,186 | 22,278,937 bytes | history encoder/fusion; one 18-value head |
| v4.0 CF (`4.0f/g`) | 5,537,560 | 22,152,098 bytes | no history encoder; four horizon heads |
| v4.0 PCF (`4.0a/c`) | 5,572,696 | 22,294,349 bytes | history encoder/fusion plus four heads |
| v4.1 PC (`4.1p/r`) | 5,537,460 | 22,155,306 bytes | corrected history path; one 18-value head |
| v4.1 CF (`4.1f/g`) | 5,537,560 | 22,152,098 bytes | corrected loss; same graph size as v4.0 CF |
| v4.1 PCF (`4.1a/c`) | 5,544,480 | 22,186,394 bytes | corrected history path plus four heads |

The file size is approximately four bytes per FP32 weight plus graph metadata. “5.5 million parameters” and “about 22 MB” therefore describe the same model, not conflicting counts.

## Training Runs and Models

| W&B run | Final epoch | Validation-selected model | ONNX output |
|---|---|---|---|
| `4.0pr` | `4.0p` | `4.0r`, epoch 9 | `[batch,1,18]` |
| `4.0fg` | `4.0f` | `4.0g`, epoch 7 | `[batch,4,18]` |
| `4.0ac` | `4.0a` | `4.0c`, epoch 7 | `[batch,4,18]` |
| `4.1pr` | `4.1p` | `4.1r` | `[batch, 1, 18]` |
| `4.1fg` | `4.1f` | `4.1g` | `[batch, 4, 18]` |
| `4.1ac` | `4.1a` | `4.1c` | `[batch, 4, 18]` |

These are six training runs and twelve checkpoints. Each pair contains the final-epoch model and the trainer-selected validation model from the same run. The suffix records how the model was selected; it does not guarantee better physical driving.

## Corrected Shared Evaluation

All 52 checkpoints from Series 1 through Series 4.1 were scored on the same 6,952-frame frozen Series 3/4 challenge subset.

| Model | Bal9 | Turn exact | Turn +/-1 | ST exact | MAE | Median | Signed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `4.0p` | **34.5%** | **32.1%** | **65.9%** | 67.7% | 12.396 | 2.967 | +0.120 |
| `4.0r` | 32.9% | 27.4% | 62.6% | **77.6%** | 11.636 | 1.846 | -1.136 |
| `4.0f` | 25.4% | 23.5% | 56.4% | 62.8% | 15.623 | 6.723 | +1.057 |
| `4.0g` | 20.4% | 17.1% | 46.4% | 76.0% | 14.116 | 2.114 | -1.864 |
| `4.0a` | 33.5% | 30.9% | 65.3% | 68.1% | 12.379 | 3.115 | +0.290 |
| `4.0c` | 32.0% | 29.4% | 62.9% | 75.5% | **11.321** | **1.825** | -0.981 |

The v4.0 offline ranking did not predict the physical result. `4.0p`, `4.0r`, `4.0a`, and `4.0c` scored strongly here but echoed earlier steering predictions on the car. Image-only `4.0f` remained drivable and showed complementary wins and failures against v3.4. This is why the project uses offline metrics to choose field candidates, not to declare a winner.

The complete v4.1 metrics are in the [Series 4 Model Zoo](../model-zoo/series-4.md) and generated report. They order the corrected models for later testing but do not prove that the steering-echo failure is fixed.

## Live Runtime Contract

The Raspberry Pi 5 sends a JPEG and selected model version over the private Ethernet link. For PC and PCF, it also sends the three previous steering targets. The Jetson Orin Nano reads the ONNX input metadata:

- Image-only graph: run CF directly;
- Graph with `target_history`: feed the Raspberry Pi 5's latest three steering targets, decode horizon 0, then append that decoded target for the next inference. The first autonomous request is seeded by the last three manual targets.

The versioned TCP request carries three big-endian float32 history values alongside the selected model and JPEG. The Jetson Orin Nano validates the model input names, output shape, and history length before CUDA inference.

## Promotion Gate

Series 4.0 is trained, runtime-supported, and field-tested. None of its models replaced v3.4: `4.0f` was viable but mixed, `4.0g` was worse, and the PC/PCF models failed from steering echo. Series 4.1 is trained and offline-evaluated but still needs live integration, closed-loop replay, and supervised physical testing. The checked-in default remains v3.4.

## Possible Learned-Throttle Experiment

The current 81,237-image dataset is not suitable for learning useful variable throttle: 77,590 labels, or 95.51%, are full throttle. A new throttle head would therefore be strongly encouraged to predict full throttle almost everywhere. Series 4 remains steering-only. Learned throttle should be reconsidered only after collecting deliberate examples of normal speed, reduced speed, and stopping in varied turns and obstacle contexts.

See [Series 4 Models](../model-zoo/series-4.md), [Bal9](../../model-evaluation/offline-evaluation/bal9.md), and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).
