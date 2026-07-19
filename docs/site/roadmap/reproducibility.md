# Reproducibility

SidewalkPilot publishes code, model files, dataset releases, and evaluation reports, but it does not claim bit-for-bit reproducibility across machines.

## What Exists

| Area | Current evidence |
|---|---|
| Source | Trainers and runtime code are versioned in GitHub. |
| Data | Series 1/2, Series 3/4, and CARLA dataset repositories are published separately on Hugging Face. |
| Training | Trainer commands, fixed seeds, hyperparameters, and Weights & Biases runs record the main experiment settings. |
| Models | Named ONNX files identify each deployed or evaluated checkpoint. |
| Evaluation | `code/test_files/models/evaluate_sidewalkpilot_models.py` evaluates every checkpoint on a frozen shared subset and writes JSON plus the PDF report. |
| Deployment | The Raspberry Pi 5 selects a version and Jetson Orin Nano resolves the matching ONNX model for ONNX Runtime inference. |

## What Must Be Recorded Per Model

1. Git commit and trainer filename.
2. Dataset repository and revision.
3. Exact training command, seed, epochs, and model version.
4. Weights & Biases run ID.
5. Final and best model filenames.
6. Evaluator JSON/PDF revision.
7. Field-test conditions and verdict.

## Limits

- The image datasets do not belong in Git history.
- GPU libraries and nondeterministic kernels can prevent byte-identical reruns even with the same seed.
- Offline metrics do not replace field validation.
- v4.0 completed training, export, offline evaluation, supervised field testing, and public model-card review. v4.1 completed training, export, and offline evaluation but still needs live integration and field testing.
- TensorRT engines are not part of the present reproducibility claim.

The useful target is a traceable experiment that produces comparable behavior and metrics, not byte-identical model files on unrelated systems.
