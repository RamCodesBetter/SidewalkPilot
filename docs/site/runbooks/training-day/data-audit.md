# Data Audit

Data Audit is the training-day runbook that checks the dataset before a run starts. The rule is simple: count first, look for corrupt files, look for label bias, and decide whether the batch should count toward the goal — never train blind on a fresh capture.

## Preconditions

- Command Setup is done and the dataset roots are known.
- The base `labels.json` and any optional correction files are identified.
- New photo runs are already promoted into a dataset root or a run-JSON label file; raw runs usually start in `media/photos/YYYY_MM_DD_run_N/`.

## Steps

1. Count images and labels per root and confirm the expected 81,237-image Series 3/4 snapshot before a comparison run.
2. Find corrupt or unreadable files. A bad image can fail during data loading or remove a sample from the usable set; list and count those files before training.
3. Check label coverage against the 9 evaluation classes (HL, L, L+, SL, ST, SR, R, R+, HR). The trainer also prints a coarser seven-bucket sampler summary. Record both schemes explicitly rather than mixing their boundaries.
4. Check for a straight-heavy or directional label distribution. A model can obtain a low aggregate MAE while retaining weak turn recall. Sample images across left, center, and right and confirm labels match the intended command.
5. Confirm every Series 3/4 label has a throttle value. The shared loader expects steering and throttle and drops rows whose throttle cannot be parsed. Series 3 retains a throttle output in its graph, but the current comparison runs set `--throttle-loss-weight 0.0`; Series 4 predicts steering only. The throttle field is still required by the current loader and remains useful capture metadata.
6. Spot-check lighting, blur, exposure, camera angle, and obstruction on a random sample. Flag shadow-heavy vs bright-sun coverage since turn-in-shadow is the identified weak spot.
7. Decide whether the batch enters the next named snapshot or remains excluded, and record the reason.

## Stop condition

- Stop and fix before training if a large fraction of images are corrupt/unreadable.
- Stop if capture provenance is unknown or a known hardware bias makes the command an invalid imitation target. Record the exclusion and reason.
- Stop and ask before deleting anything. Corrupt or drift-biased batches are counted and reported, not silently deleted; deleting photos/logs/datasets needs explicit approval.

## Evidence

- Total image count and per-root counts.
- Count of corrupt/unreadable files (and their paths).
- Per-bucket steering distribution and the straight-vs-turn ratio.
- Throttle-present count vs total.
- A one-line membership decision: included/excluded, target snapshot, and reason.

## Notes

- MAE is insufficient on a straight-heavy dataset. Judge data and models with class balance, turn recall, signed error, and field behavior as well as average error.
- Report counts and quality; leave the actual photos and logs untouched unless Ram explicitly asks to move or delete them.

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
