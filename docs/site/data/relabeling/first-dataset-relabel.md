# First Dataset Relabel

The first dataset relabel is where the whole labeling workflow started. Before
this pass the very first SidewalkPilot captures had rough, drift-prone labels; the
relabel cleaned them and became the first real entries in
`steering_corrections.json`.

## What it produced

The relabel is recorded as two `Dmmdd`-tagged sources in the finalized Series 1/2
corrections file:

| Source | Count |
|---|---:|
| `D0328_first_dataset_relabel` | 315 |
| `D0329_first_dataset_relabel` | 413 |

Together that is 728 corrected entries — the largest single provenance group in
the Series 1/2 dataset, and the two oldest sources by date. These are the frames
I went back through by hand and gave a clean steering label (0 = hard left,
90 = center, 180 = hard right).

## Why relabel the first dataset

The earliest labels came straight off early driving and were noisy — steering that
drifted or over-corrected got baked into the labels. Rather than throw those
frames away, I relabeled them: I set the steering each frame *should* have had and
wrote that as a correction. Because the trainer lets a correction override the
base label for the same image, this fixed the data without re-shooting a single
frame.

## How it fits the workflow

This pass established the pattern every later capture follows (see the
[workflow](workflow.md)): give each corrected frame an `image` path, a fixed
`steering` value, a `repeat` weight, and a `Dmmdd` `source` tag, then merge into
`steering_corrections.json`. The `D0328`/`D0329` naming keeps these two days
chronologically first in the source history, ahead of the later
street-test, curve, shadow, and v2.3 field-run sources.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/dmmdd-naming.md`
- `ai-and-models/training-pipeline/input-labels.md`
