# PC to Mac

Pulling the results of a training run — new model checkpoints and any exported artifacts — from the NVIDIA PC back to the Mac, so the Mac has the canonical copy for git, Hugging Face publishing, and deployment to the field devices. This is the return leg of a training day and, like every sync here, it is additive: nothing gets deleted on either machine.

## Preconditions

- The PC has finished training and written the new checkpoint. Series 1/2 checkpoints follow `SidewalkPilot-vX.Y[b].pth` and live under `code/ai_models/`. Series 3 exports the ONNX that Jetson Orin Nano runs; it is copied to Jetson Orin Nano separately and does not go on the Raspberry Pi 5.
- The Mac is on the model branch (`ai_models_v3`) so the checkpoint lands next to the versions already tracked there.
- I know exactly which files I want. A training day can leave several intermediate epoch files behind; I only pull the ones I mean to keep and publish.

## Steps

1. **Bring code/config back through git, not rsync.** Any trainer edits, corrections JSON, or config changes made on the PC come back via git.

   ```bash
   # NVIDIA PC
   git -C ~/rc_car_code add code/ai_models_datasets/... && git -C ~/rc_car_code commit -m "..." && git -C ~/rc_car_code push origin ai_models_v3
   # Mac
   git -C ~/rc_car_code fetch origin && git -C ~/rc_car_code checkout ai_models_v3 && git -C ~/rc_car_code pull
   ```

2. **Dry-run the checkpoint pull.** `-avn` first so I can read every file that would move.

   ```bash
   # PC -> Mac, dry run, named checkpoint(s) only
   rsync -avn <user>@<pc>:~/rc_car_code/code/ai_models/SidewalkPilot-v3.3.pth \
     ~/rc_car_code/code/ai_models/
   ```

3. **Run the real pull — named files only, no `--delete`.**

   ```bash
   rsync -av <user>@<pc>:~/rc_car_code/code/ai_models/SidewalkPilot-v3.3.pth \
     ~/rc_car_code/code/ai_models/
   ```

4. **Verify the checkpoint is intact** before committing: confirm the file size is non-zero and matches the PC, and (planned) checksum both ends. Then track it in git and, when it is field-ready, publish to Hugging Face (`ram-shreyas-naik-sabavat`).

## Stop condition

- Abort if the dry run shows a delete, a whole-`code/ai_models` mirror, or any reverse `--delete`. Model checkpoints are never overwritten or removed by a sync side effect.
- Abort if the transferred file size does not match the source — a truncated `.pth` is worse than no copy because it looks present.

## Cleanup

- Leftover intermediate epoch checkpoints on the PC are data; leave them unless Ram says to remove them. Do not delete to reclaim space during a normal pull.
- If a `.pth` arrives truncated, re-pull the single file; do not delete the partial and re-mirror the folder.

## Notes / history

- Retain both final and best-validation checkpoints. Shortlist with Bal9, turn metrics, confusion balance, MAE, and signed error; publish field claims only after a supervised drive.
- The reverse whole-repo `mrpisync` with `--delete` is the recorded hazard: it has produced docs/site/site deletion when the source lacked those trees. A checkpoint pull must always be scoped to the exact files.

## Evidence to attach

- Dry-run (`rsync -avn`) output
- Checkpoint filename + size on both ends
- Branch status on both ends
- Model/data version being pulled

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
