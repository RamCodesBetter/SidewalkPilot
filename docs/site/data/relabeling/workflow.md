# Relabeling Workflow

Relabeling changes a reviewed target without changing the captured image. The
current workflow distinguishes base-dataset edits from optional correction-file
overrides.

## Capture and Promotion

```text
field run
  -> JPEG files + append-only <run>_labels.csv
  -> finalized <run>.json
  -> review and integrity audit
  -> promoted images + sidewalkpilot_dataset/labels.json entries
```

The live runtime records logical steering degrees and absolute physical throttle
fractions. When a capture run ends, `finalize_photo_run()` converts its CSV into
the run JSON. Promotion into the Series 3/4 dataset must preserve the image/run
identity and temporal ordering.

## Two Review Paths

1. **Before a dataset snapshot is published:** correct the reviewed label in the
   working dataset build, record what changed, and regenerate the snapshot audit.
   Keep the original capture run as source evidence.
2. **After a base snapshot must remain immutable:** write an explicit correction
   file and pass it with `--corrections`. The trainer resolves correction image
   paths, skips matching base rows, and loads the corrected row with optional
   `repeat` weighting.

The current Series 3/4 repository contains the base `labels.json` and no
`steering_corrections.json`. Correction support is implemented, but its use in a
training run must be demonstrated by that run's command and scan log.

## Review Rules

- Use logical steering degrees from 0 to 180.
- Use absolute physical throttle from 0.0 to 1.0 for Series 3 records.
- Do not encode servo trim or reference-throttle mapping into a label.
- Do not infer human, autonomous, or CARLA provenance from parser behavior.
- Preserve the original image and capture record; document exclusions instead of
  silently deleting files.

## Verification

The trainer reports used, missing, bad, converted/clipped, overridden, and source
counts. A correction run should show both the expected overridden base count and
the expected correction count. Re-run the common evaluator after changing a
published comparison set.

## Related Pages

- [Dataset Overview](../dataset-overview.md)
- [Merge Rules](merge-rules.md)
- [Correction Schema](../../data-governance/labeling/correction-schema.md)
