# NVIDIA PC

The NVIDIA PC is the training and simulation workstation. It is where the Series 1/2 and Series 3 trainers run, where datasets are assembled, and where GPU-heavy experiments happen before a model is exported for the field. It is not part of the live driving loop.

## How it works

The PC hosts the training code under `code/ai_models_datasets/`:

- `series_1_and_2/sidewalkpilot_trainer.py` trains the `SteeringAutonomyV2` regression model (~0.67M params, 200x66 input, single tanh steering output) that runs on the Raspberry Pi 5.
- `series_3_and_4/series_3_sidewalkpilot_trainer.py` trains `SidewalkPilotV3` (~5.5M params, 320x180 input) with the hybrid head: 9 steering-class logits + 9 per-class offsets + 1 throttle.
- Three Series 4 trainers implement PC, CF, and PCF experiments against the same Series 3/4 dataset.

The nine Series 3 steering buckets are HL, L, L+, SL, ST, SR, R, R+, and HR. The Series 3/4 trainers read the selected dataset roots and can optionally accept explicit correction paths. The current Series 3/4 dataset uses `sidewalkpilot_dataset/labels.json` and no checked-in correction file. CARLA data, when listed as a root, enters as pre-generated files; the trainers do not drive the simulator.

Once trained, a model reaches the field two ways:

- **Series 1/2**: the `.pth` is copied into `code/ai_models` on the Raspberry Pi 5 and selected with `car` followed by dashboard model selection.
- **Series 3/4**: the version is registered in `STEERING_MODEL_VERSIONS` and the `.onnx` is copied to Jetson Orin Nano. Jetson Orin Nano answers inference over the direct Ethernet link at `10.42.0.2:8770`.

## Why this choice

- The heavy Series-3 model needs a GPU that neither the Raspberry Pi 5 nor a laptop has; the PC supplies that for training, and the Jetson Orin Nano supplies it for inference. The Raspberry Pi 5 stays dedicated to real-time I/O.
- Keeping Series 1/2 and Series 3 trainers in separate directories prevents correction-JSON and checkpoint-naming crossover between the two very different architectures.

## Key finding to remember

MAE is insufficient for these models because the common set is straight-heavy. Judge a checkpoint with confusion balance, Bal9, turn metrics, signed error, and field testing. Targeted turn-in-shadow collection is the current response to the observed shadow failure; augmentation settings alone are not field evidence.

## Verification

```bash
# NVIDIA PC: confirm the trainers compile after an edit
python3 -m py_compile code/ai_models_datasets/series_1_and_2/sidewalkpilot_trainer.py
python3 -m py_compile code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py
```

## Failure and recovery

- **Trainer picks the wrong labels or corrections**: confirm the dataset root and printed scan counts. Series 1/2 has a checked-in `steering_corrections.json`; the current Series 3/4 repository uses `sidewalkpilot_dataset/labels.json` and has no checked-in corrections file.
- **Deployed model does not load on the Raspberry Pi 5**: the version string must be present in `STEERING_MODEL_VERSIONS` in `vision.py` and the checkpoint must exist in `code/ai_models`.

Field-test verdicts are tracked with model evaluation, not inferred from a training run. The July 13 comparison rejected v3.3/v3.3b and selected v3.4. Series 4 still awaits field testing.

## Evidence to attach

- Training run config / log
- Compile log after a trainer edit
- Confusion-matrix / bucket summary for the checkpoint under review

## Related pages

- `operations/mac-pc-sync.md`
- `runbooks/sync-day/sync-verification.md`
- `publishing/mkdocs-site.md`
