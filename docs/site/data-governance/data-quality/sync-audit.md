# Sync Audit

The rule that when photo/log data moves between machines (Raspberry Pi 5 capture device, Mac workstation, Jetson Orin Nano, training PC), every source frame arrives intact and nothing is silently deleted. Data quality is not only about label correctness — a batch that got half-copied or wiped by a bad sync flag is a quality failure too.

## How it works

Photos originate on the Raspberry Pi 5. `take_photo()` queues each JPG and appends its command label under a per-day, per-run folder created by `create_photo_run_dir()` in `code/controller/current/rc_car_app/runtime.py`, named `YYYY_MM_DD_run_N`. `finalize_photo_run()` builds the JSON manifest, and `cleanup_photo_run_dir()` removes a run folder only if it is empty.

Moving those folders off the Raspberry Pi 5 is the risky step. The project has a hard-won rule: never use reverse whole-repo `rsync --delete`. It has already caused docs/site/site trees to be deleted when the remote did not contain them — the `--delete` flag treats "missing on source" as "delete on destination." The `rpisync` helper pushes local branch code to the Raspberry Pi 5; the `mrpisync` alias pulls the whole remote tree back and is the dangerous one when combined with `--delete`.

So a sync audit is a before-and-after integrity check around any data move:

1. Count files on the source run folder before the sync (photos and label JSON).
2. Sync only the target folders — `media/photos/YYYY_MM_DD_run_N/` — not the whole repo, and without `--delete` on a reverse pull.
3. Count files on the destination after and confirm the counts match.

Use the source filesystem and finalized label file for the count. The old `PRUN` and `PALL` dashboard pages were removed and are not a verification source.

## Why it matters

A truncated or partially-synced batch is indistinguishable from a small batch until the trainer scans it and reports a low `used` count or a wall of `skipped_missing` rows (labels whose images never made it across). Worse, a reverse `--delete` can destroy data or generated docs that only existed on one side. Because photos, logs, datasets, and checkpoints are never to be staged, deleted, or renamed without Ram's explicit say-so, sync integrity is the guardrail that keeps an automated copy from doing it by accident.

## Good vs bad example

- Good: `rsync -a` (no `--delete`) of just `media/photos/2026_07_02_run_1/` from Raspberry Pi 5 to Mac, then a file-count diff confirming source and destination match.
- Bad: a reverse `rsync -a --delete` of the whole repo from a machine that lacks `docs/site/` — it deletes the docs tree on the destination. This is the exact failure mode already recorded in the repo rules.

## Validation command

Compare counts across a link (label paths not present on the destination are the leak indicator). On the Raspberry Pi 5 source:

```bash
find /home/rsabavat/rc_car_code/media/photos/2026_07_02_run_1 -type f | wc -l
```

Then the same `find | wc -l` on the destination copy and diff the two numbers. To catch labels that point at missing images after a partial copy, run the trainer scan (see Image Quality Checks) and confirm `missing=0`.

## Recovery step

- Count mismatch (destination short): re-pull only the affected run folder with `rsync -a` and no `--delete`; never reverse-sync the whole tree.
- Accidental deletion from a reverse `--delete`: stop, restore from the other machine's copy, and drop the `--delete` flag before retrying. Do not clean untracked logs/photos during normal work.

Always sync photo/log folders explicitly; never rely on a whole-repo mirror.

## Evidence to attach

- Source and destination file counts, before and after.
- The trainer scan `missing=` line proving no labels lost their images.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
