# Series 4 Temporal Experiments

Series 4 asks whether steering targets near an image improve the current steering prediction. It reuses the v3.4 visual backbone and the same 81,237 real labeled images. It is an experiment alongside Series 3, not an automatic replacement.

## Three Contracts

At time `t`, the dataset pairs image `I_t` with the operator's steering target `s_t`.

| Contract | Runtime input | Training supervision |
|---|---|---|
| PC | `I_t` and `[s_(t-3), s_(t-2), s_(t-1)]` | `s_t` |
| CF | `I_t` | `[s_t, s_(t+1), s_(t+2), s_(t+3)]` |
| PCF | `I_t` and `[s_(t-3), s_(t-2), s_(t-1)]` | `[s_t, s_(t+1), s_(t+2), s_(t+3)]` |

Future targets are supervision only. The deployed model never receives future steering values. The intended prediction from every contract is horizon 0, which estimates `s_t` from the information available at time `t`.

## Shared Data Contract

All six 4.0 and six 4.1 checkpoints use:

- 81,237 real field images;
- 320x180 normalized OpenCV BGR input;
- the Series 3 six-layer convolutional backbone;
- nine steering classes plus a local offset inside each class;
- 25 training epochs and batch size 256;
- three previous targets for PC/PCF and three future targets for CF/PCF; and
- temporal windows that stay inside one capture run, one train/validation split, and a 0.25-second maximum timestamp gap.

The captured labels are approximately 10 Hz, so three steps represent roughly 0.3 seconds of labeled steering history. They are not three 30 FPS camera frames.

## Shared Visual Network

The image backbone produces 160 feature maps. Adaptive pooling to `6x10`, flattening, and dense layers create a 256-value visual feature. Each output horizon contains 18 values:

- values 0-8: logits for `HL, L, L+, SL, ST, SR, R, R+, HR`;
- values 9-17: one raw local offset for each class; and
- decoded steering: selected bucket's lower edge plus `sigmoid(selected_offset) * bucket_width`.

PC emits `[batch,1,18]`. CF and PCF emit `[batch,4,18]`. Series 4 does not learn throttle.

## Series 4.0 Architecture

For 4.0 PC/PCF, the three absolute steering targets are normalized as `(s - 90) / 90`, encoded through `3 -> 32 -> 64`, concatenated with the 256-value visual feature, and fused through `320 -> 128 -> 64`. CF uses image features only. One `64 -> 18` head is used per horizon.

| Contract | Parameters | FP32 ONNX size | Difference from Series 3 |
|---|---:|---:|---|
| Series 3 v3.4 | 5,534,115 | 22,136,200 bytes | visual backbone plus one 19-value head |
| 4.0 PC | 5,569,186 | 22,278,937 bytes | absolute-history encoder/fusion; one 18-value head |
| 4.0 CF | 5,537,560 | 22,152,098 bytes | image only; four horizon heads |
| 4.0 PCF | 5,572,696 | 22,294,349 bytes | absolute-history encoder/fusion; four heads |

The ONNX file is about four bytes per FP32 parameter plus graph metadata. A model with about 5.5 million parameters therefore occupies about 22 MB.

## Why 4.0 History Failed

Offline evaluation favored 4.0 PC/PCF, but `4.0p/r/a/c` repeated prior predictions on the car. Once the model produced a large turn, that prediction entered the next history input and could reinforce itself even when the image changed. The open-loop evaluator feeds ground-truth history, while live driving feeds earlier model predictions. That difference exposed the failure.

The image-only `4.0f` did not have this feedback path. It remained viable and showed complementary wins and failures versus v3.4. `4.0g` was worse than `4.0f`.

## Series 4.1 Corrections

Series 4.1 keeps the same questions but changes the parts implicated by the failure.

### PC and PCF History

- Encode bounded steering motion instead of allowing unrestricted fusion of three absolute targets.
- Use a bounded residual so history can adjust the image prediction but cannot dominate it without limit.
- Corrupt history during training with noise, dropped elements, sequence dropout, and random-walk noise.
- Train on counterfactual histories so changing history while keeping the image fixed does not reward blind echo.
- Include closed-loop rollout error in best-checkpoint selection.

### CF and PCF Future Supervision

- Weight the current horizon most strongly.
- Decay the contribution of later horizons.
- Penalize incorrect changes between adjacent predicted horizons with a trajectory-delta loss.

| Contract | 4.1 parameters | Output |
|---|---:|---|
| PC (`4.1p/r`) | 5,537,460 | `[batch,1,18]` |
| CF (`4.1f/g`) | 5,537,560 | `[batch,4,18]` |
| PCF (`4.1a/c`) | 5,544,480 | `[batch,4,18]` |

## Runs

| Run | Final checkpoint | Best checkpoint | Best epoch | Training status |
|---|---|---|---:|---|
| `4.0pr` | `4.0p` | `4.0r` | 9 | field-tested; history echo |
| `4.0fg` | `4.0f` | `4.0g` | 7 | field-tested; `4.0f` viable |
| `4.0ac` | `4.0a` | `4.0c` | 7 | field-tested; history echo |
| `4.1pr` | `4.1p` | `4.1r` | 1 | trained/exported; field pending |
| `4.1fg` | `4.1f` | `4.1g` | 15 | trained/exported; field pending |
| `4.1ac` | `4.1a` | `4.1c` | 10 | trained/exported; field pending |

## Runtime Status

The live selector supports 4.0. At autonomy start, PC/PCF history is seeded from the latest three manual steering targets rather than fixed straight values. After each prediction, horizon 0 becomes the newest history value.

The six 4.1 models are trained and exported but are not yet registered in the live selector. Before a 4.1 field test, the server must support their signatures and the history models must pass a closed-loop bench replay that specifically checks for the 4.0 steering-echo failure.

See [Series 4 Models](../model-zoo/series-4.md), [Bal9](../../model-evaluation/offline-evaluation/bal9.md), and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).
