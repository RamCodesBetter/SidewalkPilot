# Training Command Setup

Prepare a training run from recorded inputs instead of memory.

## Preconditions

- NVIDIA training PC with the intended CUDA/PyTorch environment.
- Correct branch and clean trainer changes.
- Populated dataset root and readable labels.
- Known dataset snapshot and frozen split identity.
- W&B authentication when online logging is required.
- New output names that do not overwrite an artifact being preserved.

## Series 3 Example

From `code/ai_models_datasets/series_3_and_4/`:

```bash
python3 series_3_sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
  --model-version 3.x \
  --epochs 35 \
  --flip-aug-probability 0.5 \
  --throttle-loss-weight 0.0 \
  --keep-pth
```

This is a command pattern, not a claim that every v3 checkpoint used those flags. Run `--help` against the exact commit before training.

## Series 4 Commands

The PC, CF, and PCF wrappers share common code and default to the experiment configuration documented on the Series 4 page. Run one wrapper per W&B experiment:

```bash
python3 series_4_0pr_sidewalkpilot_trainer.py --roots sidewalkpilot_dataset --epochs 25 --keep-pth
python3 series_4_0fg_sidewalkpilot_trainer.py --roots sidewalkpilot_dataset --epochs 25 --keep-pth
python3 series_4_0ac_sidewalkpilot_trainer.py --roots sidewalkpilot_dataset --epochs 25 --keep-pth
```

## Record Before Launch

- Command line;
- Git commit;
- Dataset repository/revision and image count;
- Split identity;
- Python/PyTorch/CUDA environment;
- GPU model;
- Seed;
- W&B run name/ID;
- Intended final and best artifact names.

Abort if CUDA is unexpectedly unavailable, labels fail the audit, roots are empty, or output names collide with artifacts that must be retained.

See [Data Audit](data-audit.md), [During Training](during-training.md), and [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md).
