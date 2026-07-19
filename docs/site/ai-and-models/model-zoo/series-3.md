# Series 3 Models

Series 3 moved inference to the Jetson Orin Nano, increased image input to `320x180`, and introduced the hybrid steering head in v3.1. The table below uses the corrected common evaluation: every checkpoint was run on the same **6,952-frame frozen Series 3/4 challenge subset**. These are held-out replay metrics, not physical-car results.

## Shared Challenge Metrics

| Model | Bal9 | Turn exact | Turn +/-1 | ST exact | MAE | Median AE | Signed | Field status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 3.0 | 16.7% | 16.5% | 45.8% | 23.5% | 18.187 | 13.122 | -2.279 | Historical |
| 3.0b | 16.2% | 15.6% | 44.6% | 26.3% | 17.573 | 12.629 | -2.586 | Historical |
| 3.1 | 28.8% | 27.2% | 55.5% | 55.7% | 22.232 | 9.440 | -3.113 | Historical |
| 3.1b | 28.2% | 25.2% | 53.8% | 57.1% | 20.590 | 9.333 | -4.510 | Historical |
| 3.2 | 26.1% | 24.3% | 55.1% | 51.0% | 17.461 | 9.727 | -1.454 | Previous baseline |
| 3.2b | 21.0% | 15.4% | 43.9% | 67.6% | 14.640 | 5.127 | -4.539 | Previous baseline |
| 3.3 | 23.8% | 18.5% | 47.7% | 65.3% | 15.168 | 6.130 | -5.411 | Went farther than 3.3b, but performed worse than 3.2 in the shadow test |
| 3.3b | 19.0% | 8.6% | 36.9% | 79.2% | 16.078 | 1.897 | -8.194 | Left the sidewalk in shadow within about 10 m; much worse than 3.2b |
| **3.4** | **24.2%** | **22.6%** | **56.2%** | 64.2% | 15.083 | 6.069 | **+0.418** | **Field-selected baseline** |
| 3.4b | 22.4% | 19.1% | 51.2% | **72.7%** | **13.985** | **2.478** | -1.566 | Slightly worse than 3.4 in field |

## Why v3.4 Won

v3.4b has lower MAE, lower median error, and higher straight recall. v3.4 has stronger turn exact, turn-within-one-bucket, and near-zero signed error. More importantly, v3.4 completed every shadow case presented in the July 13 physical comparison. That combined evidence is more relevant to steering than any isolated column.

v3.3 and v3.3b are useful negative results. They were trained to improve shadow robustness, but the physical car became worse. Stronger augmentation is not automatically better if it obscures geometry needed for real turns.

## Model Contract

- Model file: `code/ai_models/SidewalkPilot-v<version>.onnx`
- Input: `[batch,3,180,320]`, normalized OpenCV BGR
- v3.0/v3.0b output: `[batch,2]` steering and throttle regression
- v3.1+ output: `[batch,19]` = 9 logits + 9 offsets + throttle
- Runtime default: `DEFAULT_STEERING_MODEL_CHOICE = "3.4"`
- Deployment: ONNX Runtime CUDA on Jetson Orin Nano

See the [Series 4 table](series-4.md) for the temporal experiments and the [full PDF report](../../steering_model_report.pdf) for confusion matrices and all 52 checkpoints.
