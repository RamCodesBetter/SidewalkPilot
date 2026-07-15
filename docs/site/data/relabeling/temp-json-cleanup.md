# Temporary JSON Cleanup

Relabeling can produce per-run exports, review fragments, and backup JSON files.
Cleanup means removing a scratch file only after its accepted content exists in
the authoritative label source and the retained source has been validated.

## Authoritative source by family

| Family | Current authoritative labels |
|---|---|
| Series 1/2 | `series_1_and_2/steering_corrections.json` |
| Series 3/4 | `series_3_and_4/sidewalkpilot_dataset/labels.json` |

The Series 3/4 trainer supports optional correction files, but no correction file
is part of the current checked-in Series 3/4 dataset. A scratch fragment must not
be renamed into an active correction file merely because the loader supports it.

## Cleanup rule

1. Validate image paths, numeric ranges, duplicate keys, and row counts in the
   proposed authoritative file.
2. Preserve the dataset snapshot or commit that records the accepted change.
3. Confirm the trainer scans the expected rows.
4. Remove only redundant scratch or backup JSON files.

Images, runtime CSV logs, and field evidence are not temporary relabeling files.
They are never removed by this procedure.

## Related pages

- [Dataset Overview](../dataset-overview.md)
- [Merge Rules](merge-rules.md)
- [Active Label Set](../../data-governance/dataset-versioning/active-label-set.md)
