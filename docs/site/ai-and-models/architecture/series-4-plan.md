# Series 4 Temporal Experiments

Series 4 asks whether steering targets from nearby moments add useful information beyond one camera frame. It is a parallel research track built from the v3.4 visual backbone, not a replacement declared in advance.

## Experimental Question

The existing capture stream pairs an image at time `t` with the operator's target steering command `s_t`. Series 4 compares three ways to use that sequence:

| Name | Contract | Runtime input | Training supervision |
|---|---|---|---|
| PC | past + current | image `I_t` and `[s_t-3, s_t-2, s_t-1]` | `s_t` |
| CF | current + future | image `I_t` only | `[s_t, s_t+1, s_t+2, s_t+3]` |
| PCF | past + current + future | image `I_t` and `[s_t-3, s_t-2, s_t-1]` | `[s_t, s_t+1, s_t+2, s_t+3]` |

“Future” is supervision, not a future input. At deployment the car never receives labels from the future. CF and PCF use future targets only to shape a visual representation that must explain the direction the operator takes over the next samples.

## Controlled Design

All three runs used:

- The same 81,237-image real Series 3/4 dataset;
- The same frozen base split derived from contiguous 100-sample windows before temporal-window filtering;
- 320x180 normalized OpenCV BGR images;
- The same six-layer Series 3 convolutional backbone;
- The same nine steering buckets and within-bucket offset representation;
- 25 epochs, batch size 256, and 50,000 weighted samples per epoch;
- The same shadow augmentation and deterministic left/right balancing policy;
- Three previous targets and, where applicable, three future targets.

Temporal windows never cross a capture run, a train/validation boundary, or a timestamp gap greater than 0.25 seconds. The existing labeled captures are approximately 10 Hz, so three steps mean roughly 0.3 seconds of context, not three 30 FPS camera frames.

## Architecture

The visual backbone produces 160 feature maps. Adaptive pooling to `6x10`, flattening, and two dense layers produce a 256-value image feature.

For PC and PCF, the three steering targets are normalized as `(s - 90) / 90`, then encoded by `3 -> 32 -> 64` dense layers. The 256 image features and 64 history features are concatenated into 320 values and fused through `320 -> 128 -> 64`.

CF has no history branch. Its image feature goes through `256 -> 64`.

Each horizon has its own `64 -> 18` head:

- Values 0-8: logits for `HL, L, L+, SL, ST, SR, R, R+, HR`;
- Values 9-17: one raw local offset for each class;
- Decoded steering: lower bucket edge plus `sigmoid(selected_offset) * bucket_width`.

PC emits shape `[batch,1,18]`. CF and PCF emit `[batch,4,18]`. Only horizon 0 commands live steering. Series 4 intentionally removes learned throttle.

## Size

| Contract | Parameters | FP32 ONNX size | Why it differs |
|---|---:|---:|---|
| Series 3 v3.4 | 5,534,115 | 22,136,200 bytes | visual backbone + 19-value head |
| PC (`4.0p/r`) | 5,569,186 | 22,282,240 bytes | adds history encoder/fusion; one 18-value head |
| CF (`4.0f/g`) | 5,537,560 | 22,155,264 bytes | no history encoder; four small horizon heads |
| PCF (`4.0a/c`) | 5,572,696 | 22,294,528 bytes | history encoder/fusion plus four heads |

The file size is approximately four bytes per FP32 weight plus graph metadata. “5.5 million parameters” and “about 22 MB” therefore describe the same model, not conflicting counts.

## Runs and Artifacts

| W&B run | Final epoch | Best current-target MAE | ONNX outputs |
|---|---|---|---|
| `4.0pr` | `4.0p` | `4.0r`, epoch 9 | `[batch,1,18]` |
| `4.0fg` | `4.0f` | `4.0g`, epoch 7 | `[batch,4,18]` |
| `4.0ac` | `4.0a` | `4.0c`, epoch 7 | `[batch,4,18]` |

These are three training runs and six checkpoints. The paired letter is the lowest-current-target-MAE checkpoint from the same run; it is not automatically the best field model.

## Corrected Shared Evaluation

All six checkpoints and all 40 Series 1-3 checkpoints were scored on the same 6,952-frame frozen Series 3/4 challenge subset.

| Model | Bal9 | Turn exact | Turn +/-1 | ST exact | MAE | Median | Signed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `4.0p` | **34.5%** | **32.1%** | **65.9%** | 67.7% | 12.396 | 2.967 | +0.120 |
| `4.0r` | 32.9% | 27.4% | 62.6% | **77.6%** | 11.636 | 1.846 | -1.136 |
| `4.0f` | 25.4% | 23.5% | 56.4% | 62.8% | 15.623 | 6.723 | +1.057 |
| `4.0g` | 20.4% | 17.1% | 46.4% | 76.0% | 14.116 | 2.114 | -1.864 |
| `4.0a` | 33.5% | 30.9% | 65.3% | 68.1% | 12.379 | 3.115 | +0.290 |
| `4.0c` | 32.0% | 29.4% | 62.9% | 75.5% | **11.321** | **1.825** | -0.981 |

PC is the strongest first field candidate because `4.0p` leads the class-balanced and turn metrics. PCF is close and has the best raw-error checkpoint. CF did not show the same benefit in this offline comparison. That result does not isolate the temporal contract from checkpoint selection or prove that future-target supervision is generally inferior.

## Live Runtime Contract

The Raspberry Pi 5 still sends only the JPEG and selected model version over the private Ethernet link. Jetson Orin Nano reads the ONNX input metadata:

- Image-only graph: run CF directly;
- Graph with `target_history`: feed the Raspberry Pi 5's latest three steering targets, decode horizon 0, then append that decoded target for the next inference. The first autonomous request is seeded by the last three manual targets.

The versioned TCP request carries three big-endian float32 history values alongside the selected model and JPEG. The Jetson Orin Nano validates the model signature and history length before inference. CUDA is selected without registering a partially installed TensorRT provider that could force an accidental CPU fallback.

## Promotion Gate

Series 4 is **trained and runtime-supported**, but **not field-selected**. It must beat v3.4 on the same physical shadow/turn route, remain smooth under autoregressive history, satisfy inference-freshness checks, and preserve AEB behavior before the live default changes.

See [Series 4 Models](../model-zoo/series-4.md), [Bal9](../../model-evaluation/offline-evaluation/bal9.md), and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).
