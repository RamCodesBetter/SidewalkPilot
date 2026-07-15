# Merge Rules

These rules describe the optional correction merge implemented by both trainer
families.

## 1. Match by Resolved Image Path

The loader resolves every correction image before scanning base roots. A base
sample with the same resolved path is skipped and counted as overridden. The
correction becomes the only active label for that path.

## 2. Keep One Correction Per Image

Multiple correction rows for one image are ambiguous. Use one reviewed row and,
if justified, its `repeat` value. `repeat` creates repeated in-memory samples; it
does not create new visual evidence.

## 3. Match the Family Schema

- Series 1/2 corrections require an image reference and steering.
- Series 3 corrections require an image reference, steering, and throttle.
- Series 4 trains from the Series 3/4 base records; future targets are derived
  supervision and are not written into the source labels.

## 4. Preserve Provenance Separately

The trainer tags loaded corrections as source `correction` for weighting. Any
human-readable capture source should remain in the correction metadata and in the
run record. Do not label a checkpoint real-only or CARLA-assisted unless its
saved training inputs establish that fact.

## 5. Verify Before Promotion

Read the trainer's `skipped base labels overridden by corrections` and
`corrections used/missing/bad` lines. Then re-run the evaluator and retain the
command, dataset revision, and result. A correction that improves one frame does
not by itself establish better field driving.

## Related Pages

- [Relabeling Workflow](workflow.md)
- [Correction Schema](../../data-governance/labeling/correction-schema.md)
- [Input Labels](../../ai-and-models/training-pipeline/input-labels.md)
