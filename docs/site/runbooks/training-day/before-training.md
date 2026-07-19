# Training Day

Before Training is the gate runbook: the last set of checks that must pass before the trainer is launched. It ties together Command Setup and Data Audit into a single go/no-go decision so a run is not started with a broken environment or invalid dataset.

## Preconditions

- Command Setup is complete: the exact trainer command is assembled and saved.
- Data Audit is complete: image counts, corrupt-file count, bucket balance, and the count decision are recorded.
- Training runs on the GPU box (the NVIDIA PC), not the Raspberry Pi 5 and not Jetson Orin Nano.

## Steps

1. Confirm the working directory and exact trainer:
   ```bash
   cd code/ai_models_datasets/series_3_and_4
   python3 series_3_sidewalkpilot_trainer.py --help
   ```
   For Series 4, use the matching `series_4_0*` or `series_4_1*` PC, CF, or PCF wrapper.
2. Confirm the GPU is visible:
   ```bash
   python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
3. Confirm the output versions do not collide with checkpoints you want to keep. Series 3 takes `--model-version`; each Series 4 wrapper fixes its own final/best pair.
4. Confirm the dataset roots are non-empty. If `--corrections` is supplied, confirm every correction file resolves; corrections are optional.
5. Confirm Weights & Biases is ready if the run should be logged (W&B project `Sidewalk-Pilot/SidewalkPilot`). If you do not want a logged run, note that in the run note.
6. Confirm disk space for checkpoints, ONNX export, and W&B run files.
7. Read the assembled command against the intended run: trainer family, output versions, roots, corrections, epochs, split, and augmentation settings. Run `--help` against the exact checked-out commit instead of relying on copied defaults.

## Stop Condition

- No-go if `torch.cuda.is_available()` is `False` and you expected CUDA.
- No-go if the Data Audit count decision was "do not count / known-bad" and this is meant to be a clean-goal run.
- No-go if the `--model-version` would overwrite a checkpoint you still need.
- No-go if there are no usable dataset roots.

## Evidence

- The go/no-go decision with a timestamp.
- CUDA-available output and device name.
- Confirmation that the chosen version is unused.
- Link back to the Data Audit result and the Command Setup command.

## Notes

- This runbook does not change data or code — it only decides whether to launch. If any check fails, go back to Command Setup or Data Audit; do not "fix it in the trainer command" on the fly.
- Keep logical steering thinking here: labels are logical degrees (0=left, 90=center, 180=right). Do not put physical trim compensation into training labels.

## Data Audit and Command Record

Before launch, record dataset repository/revision, image/label counts, decoder failures, missing paths, duplicate/conflict counts, steering/source distributions, split method, corrections and hashes, trainer commit, seed, epochs, and every non-default flag. Use a dry-run or dataset scan before consuming GPU time.

## During Training

Monitor train/validation loss, Bal9/class or bucket behavior, steering MAE, gradient norm, learning rate, GPU use, epoch time, and W&B state. Stop for nonfinite loss, broken logging, wrong data counts, an obvious output-version collision, or a CPU run when CUDA was required. Do not choose a model from one favorable graph while the run is incomplete.

## Export and After-Training

Preserve final and validation-selected models separately. Validate the ONNX input names, shapes, output shape, finite inference, and matching decoder. Series 4 PC/PCF require history input; CF does not. Run the common evaluator, review confusion/turn metrics, and deploy only selected candidates. Record hashes and leave field status as untested until the car is driven.

## Related Pages

- [Training Pipeline](../../ai-and-models/training-pipeline/overview.md)
- [Data Quality](../../data-governance/data-quality/image-quality-checks.md)
- [Model Selection Rubric](../../model-evaluation/comparisons/model-selection-rubric.md)
