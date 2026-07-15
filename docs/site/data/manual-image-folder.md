# Manual Image Folder

The manual image folder is the frame store each SidewalkPilot dataset is built
around: the `sidewalkpilot_dataset/` directory that holds every JPG the trainer
loads. It sits next to the label file and the trainer inside each series folder.

## What it is

Each series has its own image folder:

- `code/ai_models_datasets/series_1_and_2/sidewalkpilot_dataset/` — the finalized
  Series 1/2 frames (2,224 JPGs at audit time).
- `code/ai_models_datasets/series_3_and_4/sidewalkpilot_dataset/` — the current
  81,237-frame real-image dataset used by Series 3 and Series 4 experiments.

The folder contains the images and its own `labels.json`. Each label maps an image
name to steering and throttle values. Optional correction files may be supplied
separately with `--corrections`; they are not the primary label store.

## How the trainer reads it

The trainer takes the folder as a dataset **root** via `--roots`. For each root it
loads `labels.json` and resolves every referenced image by relative path. If an
optional correction file is supplied, a matching correction overrides the base
label and its `repeat` value controls repeated correction samples. The trainer resizes
each frame to the model input size at load time — Series 1/2 to 200x66, Series 3
to 320x180 — so the folder can safely hold mixed capture resolutions.

## Why keep images and labels separate

- **Labels are editable, frames are not.** Fixing a bad label means editing one
  JSON entry, not touching or re-shooting the image.
- **Labels stay auditable.** Steering and absolute physical throttle remain in a
  readable JSON mapping. Capture provenance is retained in the prefixed image/run
  name and should also be recorded in the dataset release metadata.
- **The same frame can be relabeled.** Because the trainer matches corrections to
  images by path, a frame in this folder can be overridden or reweighted without
  duplicating the image on disk.

## Where new frames come from

New frames start as field photo runs under `media/photos/YYYY_MM_DD_run_N/` and
are promoted into a series' `sidewalkpilot_dataset/` folder with matching label
entries. Frames are never deleted from a folder without an explicit decision;
known-bad batches (for example the 2026-06-15 left-drift hardware-bias run) are
counted and reported rather than silently removed.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/dmmdd-naming.md`
- `ai-and-models/training-pipeline/input-labels.md`
