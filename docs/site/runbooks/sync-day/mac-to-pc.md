# Mac to PC

Moving code, datasets, and captured photos from the Mac (my git and photo-pull workstation) to the NVIDIA PC (training/simulation) so a training run works from the same data I collected in the field. This is a one-directional, additive copy — it should never delete anything on either end.

## Preconditions

- The Mac holds the branch and data I want to train from. The current runtime branch is `lidar-aeb-v2`; documentation work is on `docs_series3_pages`. I confirm the intended branch and destination on both ends before copying so I do not overwrite newer code with older code.
- The photo runs I want on the PC already live under `media/photos/YYYY_MM_DD_run_N/` (each run may carry a JSON manifest). The trainer reads from the aggregate `sidewalkpilot_dataset`, so the runs have to arrive intact.
- Disk space on the PC is enough for the batch and the current 81,237-image dataset.

## Steps

1. **Sync code through git, not rsync.** Push the branch from the Mac and pull it on the PC. Git is the safe channel for source; rsync is only for the large binary data git should not carry.

   ```bash
   # Mac
   git -C ~/rc_car_code push origin ai_models_v3
   # NVIDIA PC
   git -C ~/rc_car_code fetch origin && git -C ~/rc_car_code checkout ai_models_v3 && git -C ~/rc_car_code pull
   ```

2. **Dry-run the photo copy first.** Always `-avn` (n = dry run) so I can read exactly what would move before anything is written.

   ```bash
   # Mac -> PC, ONE run folder, dry run
   rsync -avn ~/rc_car_code/media/photos/2026_07_02_run_1/ \
     <user>@<pc>:~/rc_car_code/media/photos/2026_07_02_run_1/
   ```

3. **Run the real copy — scoped to the named run folder, no `--delete`.** I copy only the folders I actually want, never the whole repo.

   ```bash
   rsync -av ~/rc_car_code/media/photos/2026_07_02_run_1/ \
     <user>@<pc>:~/rc_car_code/media/photos/2026_07_02_run_1/
   ```

4. **Verify counts match** (see `runbooks/sync-day/sync-verification.md`): `find <run_dir> -type f | wc -l` on both ends must agree, and a trainer scan on the PC should report `missing=0`.

## Stop condition

- Abort if the dry run shows a delete, a whole-repo transfer, or any path outside `media/photos/...` (code should have gone through git, not rsync).
- Abort if branches disagree in a way that means the copy would clobber newer work. Resolve in git first.

## Cleanup

- No generated artifacts to clean on a push. If a partial run folder was created by an interrupted copy, leave the files in place and re-run the same scoped rsync — do not delete to "start clean."

## Notes / history

- The everyday code-to-Raspberry Pi 5 direction is `rpisync` (pushes the local branch to the Raspberry Pi 5). That is the safe push. The dangerous alias is `mrpisync`, which pulls the whole remote tree back and can delete local files when combined with `--delete` — never use it for a Mac↔PC photo move.
- Photos, logs, datasets, and checkpoints are treated as irreplaceable data. They are never staged, renamed, or deleted as a side effect of a sync.

## Evidence to attach

- Dry-run (`rsync -avn`) output
- Branch status on both ends
- File/manifest counts before and after
- Trainer scan `missing=` line

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
