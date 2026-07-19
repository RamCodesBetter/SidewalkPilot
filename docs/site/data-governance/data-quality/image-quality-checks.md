# Image Quality Checks

A usable Series 3/4 sample needs an image that exists and decodes, a parseable logical steering label, and a parseable absolute-throttle field. The current tools check these properties in two stages: a read-only image decoder and the trainer's label scan. Neither stage automatically proves that the command is the correct human target for the scene; that still requires review.

## Capture Format

The runtime queues `photo_<timestamp>.jpg` into a dated run folder and appends the sampled command to `<run>_labels.csv`. When a capture run ends, `finalize_photo_run()` builds `<run>.json`. A finalized entry has this form:

```json
{
  "photo_20260702_141530_123456.jpg": {
    "steering": 128,
    "throttle": 0.35
  }
}
```

`steering` is the logical `0..180` command (`0` left, `90` center, `180` right). `throttle` is absolute forward physical PWM in `0.0..1.0`; physical 55% is `0.55`, not zero on the reference-throttle scale.

## Image Scan

`code/test_files/data/check_dataset_frames.py` is read-only. It:

- Verifies each JPEG header and full decode;
- Flags truncation, unexpected dimensions, near-black/near-white frames, and files smaller than 1 KiB; and
- Compares disk filenames with `labels.json` keys.

Run it against the frozen dataset folder:

```bash
python3 code/test_files/data/check_dataset_frames.py \
  code/ai_models_datasets/series_3_and_4/sidewalkpilot_dataset
```

The script does not calculate perceptual near-duplicates and does not judge whether a visually valid label is behaviorally correct.

## Trainer Label Scan

The Series 3 trainer's `SteeringDataset` reports:

- `skipped_missing`: no image path could be resolved;
- `skipped_bad`: steering or throttle could not be converted to a number;
- `clipped_labels`: steering was converted from normalized form or clamped into range; and
- `skipped_overridden`: a correction entry replaces the base row.

Run the dataset-building path without starting optimization:

```bash
cd code/ai_models_datasets/series_3_and_4
python3 series_3_sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
  --dry-run
```

`--dry-run` validates paths, labels, split construction, balancing, and class weights. It does not decode every image; use `check_dataset_frames.py` for that.

## Examples

Valid structure:

```json
{
  "photo_20260702_141530_123456.jpg": {
    "steering": 62,
    "throttle": 0.40
  }
}
```

Examples that need review:

```json
{
  "photo_missing.jpg": {
    "steering": 90,
    "throttle": 0.30
  },
  "photo_bad_label.jpg": {
    "steering": "n/a",
    "throttle": 0.30
  },
  "photo_out_of_range.jpg": {
    "steering": 240,
    "throttle": 0.30
  }
}
```

The first becomes missing if the file is absent, the second is skipped as bad, and the third is clamped and counted in `clipped_labels`; it is not automatically dropped.

## Recovery

- For missing files, first verify whether the run was partially synced or renamed. Recopy the scoped source run without reverse `--delete`, then repeat both scans.
- For bad or out-of-range labels, inspect the original run CSV and field context before changing the JSON.
- For corrupt images, preserve the report and source path. Do not delete images, labels, logs, or checkpoints without Ram's explicit approval.

## Evidence

- Complete `check_dataset_frames.py` summary
- Trainer `--dry-run` root summaries and class counts
- Dataset snapshot name, image count, label count, command, and code revision
- Any reviewed rows before and after correction

## Coverage and Leakage Review

Image integrity is only the first gate. Before training, compare steering-class counts, left and right balance, ordinary turns, turns in shadow, lighting periods, surfaces, routes, and source runs. A collection countdown may guide field work, but filling numeric buckets does not prove visual diversity.

Consecutive frames create leakage risk. Series 3/4 window splitting reduces adjacency across train/validation, while Series 1/2's historical random split can place near-neighbors on both sides. Neither result should be described as capture-run-independent unless the split is actually grouped by run.

After any computer-to-computer sync, verify image and label counts, representative hashes, missing files, and unexpected deletions before accepting the destination as a new source of truth. Reverse sync with `--delete` is especially dangerous when large datasets are excluded on one side.

## Related Pages

- [Controller Mapping and Driving Modes](../../runtime-code/controller-mapping.md)
- [Dataset Overview](../../data/dataset-overview.md)
- [Dataset Versioning](../dataset-versioning/version-rules.md)
- [Hugging Face Publishing](../../publishing/huggingface.md)
