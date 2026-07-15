# Relabel Review

Relabel review is the process rule for turning a spotted labeling mistake into a merged correction: how a wrong label is found, re-drawn, checked, and promoted into the active label set without corrupting the raw captures or the model contract. It sits between "a frame is mislabeled" and "the corrected label is in training."

## When a relabel happens

A relabel is triggered by evidence, not a hunch:

- A field failure tied to a specific, recoverable frame or capture segment.
- An evaluation signal that points at a bucket rather than one frame, such as weak left/right recall despite a low aggregate MAE.
- A duplicate or bad-label finding surfaced by the load logs (`missing`, `bad`, or an unexpected `skipped_overridden`).

## How the review works

1. **Identify the frames.** Pull the exact image(s), keep their original path and `source` tag.
2. **Re-draw the label in physical units.** Corrected `steering` in degrees (`0`=left, `90`=straight, `180`=right), and for Series 3 a corrected `throttle` in `0.00`..`1.00`. Never encode hardware trim or servo compensation into the label — that belongs in the runtime mapping layer.
3. **Preserve the original capture.** Before publishing a new snapshot, update the working label with an audit record; for an immutable base snapshot, add an explicit correction file and pass it to the trainer.
4. **Verify the selected path.** If an optional correction file is used, the raw frame must show up in `skipped_overridden` and the correction in `corrections used`. If the next published base snapshot is edited instead, verify the changed key, row count, diff, and snapshot identity.
5. **Re-evaluate before merge.** Confirm the fix moved the target buckets in the confusion matrix without collapsing the rest, then promote the correction into the active label set.

## Why this choice

Keeping the image capture immutable while versioning label changes makes review and rollback possible. A separate correction file is one available method; a new versioned base-label snapshot is another. Requiring an evaluation check before promotion limits the risk that a targeted edit silently changes broader model behavior.

## Good vs bad review

Good: a reviewed frame receives a corrected logical steering value, the change retains its source path, the loader reports the expected override when a correction file is used, and the complete comparison is re-evaluated.

Bad: a label is edited without a preserved diff or snapshot, only MAE is checked, and the change is promoted without class-level or field evidence.

## Validation

Confirm the merge with the load logs and a quick count:

```bash
cd code/ai_models_datasets/series_1_and_2
python3 -c "import json; d=json.load(open('steering_corrections.json')); print('correction_rows',len(d))"
```

Then re-run the evaluator and read the bucket confusion / turn coverage, not just the headline MAE:

```bash
python3 code/test_files/models/evaluate_sidewalkpilot_models.py --device cuda
```

## Recovery

If a relabel made things worse, restore the prior label snapshot or remove the optional correction row, then re-evaluate. If a whole batch is suspect, quarantine it and report the counts before deleting anything.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
