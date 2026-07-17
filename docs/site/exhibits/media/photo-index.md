# Photo Index

This page indexes the SidewalkPilot training-photo dataset — the raw camera frames
captured while driving, which provide the operator-command targets used to train steering
and evaluated on. It records how photos are captured, how a run is labeled, and
where the full dataset lives.

## How photos are captured

Frames come from the Raspberry Pi Camera Module 3 Wide on the Raspberry Pi 5 via Picamera2. The camera
streams at 1280x720 (`CAMERA_FRAME_WIDTH` x `CAMERA_FRAME_HEIGHT` in `vision.py`,
BGR888) and is rotated 180 degrees (`PI_CAMERA_ROTATE_180 = True`, applied as an
hflip+vflip transform). A photo is saved when the driver presses the capture button
(`PHOTO_BUTTON = 1`, the B button in the current Pygame mapping). The Menu button
toggles continuous run capture at a configured 10 fps while the car is moving.

Capture is handled by `take_photo()` in `runtime.py`:

- Photos are grouped into per-run folders named `YYYY_MM_DD_run_N`, auto-incrementing
  `N` per day (`create_photo_run_dir()`), created under `media/photos/`.
- Each frame is saved with a microsecond timestamp such as
  `photo_YYYYMMDD_HHMMSS_ffffff.jpg`.
- Labels are appended to `<run>_labels.csv` as frames are queued. When capture
  ends, `finalize_photo_run()` builds `<run>.json` with
  `{"steering": <0..180>, "throttle": <0.0..1.0 physical PWM>}`.
- Steering is stored as the **logical servo angle** (0 = left, 90 = center,
  180 = right) taken from `steering_servo_deg`; throttle is the clamped forward motor
  PWM at capture time.
- Empty run folders are removed during cleanup when no files were created.

## What each entry supports

The photo dataset is evidence behind each training claim, so an index entry
should tie a batch to its condition and its usability decision:

| Field | What to record |
|---|---|
| Run folder | `media/photos/YYYY_MM_DD_run_N` |
| Date / condition | Capture date, lighting, weather |
| Frame count | Images in the folder |
| Label manifest | `<run>.json` present? |
| Bucket coverage | L / C / R balance, turn vs straight, shadow |
| Usability | Counts toward the goal, or excluded (with reason) |

## Where the data lives

Working capture folders under `media/photos/` are intentionally untracked and vary by
machine and sync policy, so this page does not use the current checkout count as a
published dataset statistic. The **full 81,237-frame Series 3/4 dataset lives on
Hugging Face** under `ram-shreyas-naik-sabavat`; its canonical description belongs
there (see `publishing/huggingface.md`), not in a volatile local-folder inventory.

## Dataset status and exclusions

- The published Series 3/4 dataset contains **81,237 labeled real images**. Future collection is driven by repeatable field gaps, not an aggregate count target.
- Turn and turn-in-shadow balance remains a quality dimension to audit in each snapshot.
- The **2026-06-15 batch is excluded**: it was a left-drift, hardware-biased run and
  remains excluded from the reviewed dataset unless that decision is reversed. (Note:
  its run folders are present locally with manifests but no images in this checkout.)
- Data policy: count frames, flag corrupt/unreadable files, sample for
  lighting/blur/exposure/angle/obstruction and steering bias, and report before any
  deletion. Do not delete data without explicit sign-off.

## Related pages

- `exhibits/media/video-index.md`
- `exhibits/media/dashboard-screenshots.md`
- `portfolio-evidence/reader-paths/evidence-map.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
