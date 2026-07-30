# Sync Day

Moving code, datasets, and captured photos from the Mac (my git and photo-pull workstation) to the NVIDIA PC (training/simulation) so a training run works from the same data I collected in the field. This is a one-directional, additive copy — it should never delete anything on either end.

## Preconditions

- The source computer holds the branch and data intended for the destination. Confirm the exact current branch and destination on both ends rather than relying on a branch name copied into documentation.
- The photo runs I want on the PC already live under `media/photos/YYYY_MM_DD_run_N/` (each run may carry a JSON manifest). The trainer reads from the aggregate `sidewalkpilot_dataset`, so the runs have to arrive intact.
- Disk space on the PC is enough for the batch and the current 80,969-image local dataset.

## Steps

1. **Sync code through git, not rsync.** Push the branch from the Mac and pull it on the PC. Git is the safe channel for source; rsync is only for the large binary data git should not carry.

   ```bash
   # Mac
   git -C ~/rc_car_code push origin <branch>
   # NVIDIA PC
   git -C ~/rc_car_code fetch origin
   git -C ~/rc_car_code switch <branch>
   git -C ~/rc_car_code pull --ff-only
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

4. **Verify counts match:** `find <run_dir> -type f | wc -l` on both ends must agree, representative hashes should match, and a trainer scan on the PC should report `missing=0`.

## Reverse Sync and Delete Risk

Pulling PC-to-Mac follows the same rules: dry-run, scope the transfer to the named model, dataset, or run, and omit `--delete`. A whole-repository reverse mirror can remove documentation, datasets, or photos that are absent on the remote. Source code should return through Git; model and data files should return through an explicit path.

After transfer, compare counts and representative hashes, run the dataset/image audit where applicable, and inspect `git status` to ensure generated or binary data did not enter source control. If a transfer was interrupted, rerun the same additive copy rather than deleting the partial destination.

## Stop Condition

- Abort if the dry run shows a delete, a whole-repo transfer, or any path outside `media/photos/...` (code should have gone through git, not rsync).
- Abort if branches disagree in a way that means the copy would clobber newer work. Resolve in git first.

## Cleanup

- There are no generated files to clean on a push. If an interrupted copy created a partial run folder, leave the files in place and rerun the same scoped rsync; do not delete them to "start clean."

## Notes and History

- The everyday code-to-Raspberry Pi 5 direction is `rpisync` (pushes the local branch to the Raspberry Pi 5). That is the safe push. The dangerous alias is `mrpisync`, which pulls the whole remote tree back and can delete local files when combined with `--delete` — never use it for a Mac↔PC photo move.
- Photos, logs, datasets, and checkpoints are treated as irreplaceable data. They are never staged, renamed, or deleted as a side effect of a sync.

## Evidence to Attach

- Dry-run (`rsync -avn`) output
- Branch status on both ends
- File/manifest counts before and after
- Trainer scan `missing=` line

## Related Pages

- [Mac and Computer Sync](../../operations/mac-pc-sync.md)
- [Data Quality](../../data-governance/data-quality/image-quality-checks.md)
- [Training Day](../training-day/before-training.md)
