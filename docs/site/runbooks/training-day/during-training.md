# During Training

During Training is the runbook for the actual trainer run: launch it, watch the right signals, and know when to let it finish versus kill it. The trainer produces a final checkpoint and a paired best checkpoint, and optionally exports ONNX at the end.

## Preconditions

- Before Training passed its go / no-go check.
- The assembled command from Command Setup is ready.
- You are in `code/ai_models_datasets/series_3_and_4` on the GPU box.

## Steps

1. Launch the run (typical form):
   ```bash
   python3 series_3_sidewalkpilot_trainer.py \
     --roots sidewalkpilot_dataset \
     --model-version 3.x \
     --epochs 35 \
     --throttle-loss-weight 0.0 \
     --keep-pth
   ```
2. Watch the dataset scan output at the start: usable/missing/bad counts, source labels inferred from the selected roots, per-bucket steering counts, and sampler weights. Do not infer that a run used CARLA merely because the trainer supports a CARLA source weight; the launched roots and saved run log are the evidence.
3. Watch each epoch's printed metrics: loss and the EMA loss, plus the `Pred straight 85..95` count. A rising "pred straight" count while turns stay low is the straight-collapse warning sign.
4. Track the checkpoint objective. Series 3 and 4 write the paired best checkpoint when steering MAE improves, while Series 1/2 use validation loss. Final-epoch weights are saved separately.
5. Follow the W&B run if logging is on (project `Sidewalk-Pilot/SidewalkPilot`) for the loss and metric curves over time.
6. Let it run to the explicitly selected epoch count unless a stop condition triggers. The current trainer exports both final and best checkpoints to 320x180 opset-17 ONNX. `--keep-pth` preserves the PyTorch checkpoints after export.

## Stop condition

- Kill the run if loss goes NaN or explodes — check `--grad-clip` (default 1.0), learning rate, and label sanity, then restart.
- Kill the run if the "pred straight 85..95" count runs away while turn buckets stay empty — the model is collapsing to straight; this is a data/augmentation problem, not a "train longer" problem.
- Kill the run if you launched with the wrong `--model-version` and it would overwrite a checkpoint you need.
- Do not judge a run by MAE alone. A low-MAE checkpoint can still have weak turn recall on a straight-heavy dataset. Judge it with turn coverage, Bal9, and the confusion matrix.

## Evidence

- The full stdout log of the run (scan counts, per-epoch metrics, best-checkpoint saves).
- The W&B run URL if logged.
- Final `best_val` and total training time from the closing line.
- Paths of the written checkpoints (`SidewalkPilot-v3.x.pth` and `SidewalkPilot-v3.xb.pth`) and any ONNX export.

## Notes

- "best" (the `b` checkpoint) is lowest-validation-loss, which is not automatically the best driver. Field verdicts have shown the balanced final (e.g. deploy v3.3, not v3.3b; v3.3b was early-epoch straight-collapsed). Record which one you intend to deploy, and why.
- Offline curves cannot settle the turn-versus-shadow trade-off. Use them to reject obvious collapse, then compare the surviving checkpoints on the physical route.

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
