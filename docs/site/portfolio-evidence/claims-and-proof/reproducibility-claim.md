# Reproducibility Claim

The public code, datasets, model artifacts, and generated evaluator outputs expose the core SidewalkPilot software/model workflow. Reproducing the physical driving result still requires equivalent hardware, wiring, calibration, power, and a controlled route.

## Reproducible Pieces

- Runtime source and constants are versioned in GitHub.
- Series 1/2 and Series 3/4 datasets are published on Hugging Face.
- Trainers for Series 1-4 and ONNX export code are checked in.
- The common evaluator produces committed JSON and PDF artifacts.
- W&B records the Series 4 training runs.
- The model registry and dashboard make the selected checkpoint visible during a run.

## Required Run Record

A genuinely repeatable training result needs the git commit, dataset revision, split membership, full command, random seed, environment versions, W&B run ID, and artifact hash. A genuinely repeatable field result additionally needs hardware calibration, route, conditions, AEB state, clips/logs, and takeover records.

## Limits

- Published code cannot reproduce undocumented mechanical alignment or battery/load state.
- The July 13 v3.4 field verdict lacks a complete route/clip/takeover record.
- The Series 4 models are offline-evaluated but have no physical field verdict.
- Current deployment is FP32 ONNX Runtime/CUDA; no reproducibility claim depends on a TensorRT engine.

See [Evidence Map](../reader-paths/evidence-map.md) and [Retest Policy](../../engineering-process/iteration-records/retest-policy.md).
