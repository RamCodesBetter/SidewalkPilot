# Series 3 Models

Series 3 moved inference to the Jetson, increased image input to `320×180`, and introduced the hybrid steering head in v3.1. All metrics below use the 81,237-image current Series 3 real-field evaluation set and are training-set fit checks, not held-out generalization proof.

## Current Metrics

| Model | Bal9 | Turn exact | Turn ±1 | Straight exact | MAE | Median AE | Signed | Field status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 3.0 | 16.0% | 15.3% | 42.9% | 23.4% | 18.971 | 13.623 | -3.594 | Historical |
| 3.0b | 15.9% | 14.8% | 42.3% | 24.6% | 18.450 | 13.129 | -3.944 | Historical |
| 3.1 | 28.1% | 26.8% | 53.3% | 55.2% | 22.647 | 9.729 | -2.353 | Historical |
| 3.1b | 27.4% | 25.8% | 52.3% | 56.7% | 20.958 | 9.591 | -3.769 | Historical |
| 3.2 | 34.0% | 31.1% | 57.7% | 52.4% | 16.776 | 9.648 | -1.474 | Previous baseline |
| 3.2b | 25.1% | 19.8% | 46.0% | 67.2% | 14.457 | 5.909 | -4.691 | Previous baseline |
| 3.3 | 27.1% | 21.2% | 48.1% | 68.5% | 14.630 | 5.204 | -5.351 | Field regression vs 3.2 |
| 3.3b | 19.2% | 10.6% | 36.5% | 78.0% | 16.460 | 2.183 | -8.287 | Severe field regression vs 3.2b |
| **3.4** | **33.3%** | **32.6%** | **60.7%** | **65.5%** | **14.377** | **4.859** | **+0.799** | **Field-selected production model** |
| 3.4b | 25.6% | 22.7% | 52.2% | 73.7% | 13.904 | 2.678 | -2.093 | Slightly worse than 3.4 in field |

## Why v3.4 Won

v3.4 is not first in every isolated numeric column. v3.4b has lower MAE and median error, while v3.2 has slightly higher balanced exact accuracy. v3.4 has the strongest turn exact and turn-within-one-class values in the table, near-zero signed error, and the strongest recorded field behavior. That combined evidence is more relevant to steering than one aggregate error number.

The v3.3 experiment used a stronger tree-shadow augmentation regime and produced unstable field behavior. v3.4 softened and rebalanced that training approach. The result is evidence that augmentation realism and probability matter more than maximum augmentation strength.

## Artifact Contract

- Artifact: `code/ai_models/SidewalkPilot-v<version>.onnx`
- Input: `[batch,3,180,320]`, normalized OpenCV BGR
- v3.0 output: `[batch,2]`
- v3.1+ output: `[batch,19]`
- Runtime default: `DEFAULT_STEERING_MODEL_CHOICE = "3.4"`
- Deployment: ONNX Runtime CUDA on Jetson when available

Individual public cards and manifests are available under the [SidewalkPilot Hugging Face namespace](https://huggingface.co/ram-shreyas-naik-sabavat).
