# Photo Capture

Photo capture turns a live drive into image/command pairs. The Raspberry Pi queues a copy of the latest camera frame, records the logical steering command and absolute physical forward-throttle value sampled at that capture request, and groups the files into a dated run folder.

## Controls

| Control | Current behavior |
|---|---|
| Xbox B, pygame button `1` | Queue one photo |
| Xbox Menu, pygame button `11` | Toggle continuous run capture at `PHOTO_RUN_CAPTURE_FPS` (`10.0` fps) |

Continuous capture pauses while both measured speed is below `0.1 mph` and requested throttle is below `0.05`. This avoids filling a run with stationary near-duplicates while allowing capture to continue if the hall sensor temporarily reports zero during commanded motion.

## Run folder and filenames

The first capture in a process creates `media/photos/YYYY_MM_DD_run_N/`, where `N` is the next unused run index for that date. Images use microsecond timestamps:

```text
photo_YYYYMMDD_HHMMSS_microseconds.jpg
```

`take_photo()` calls `queue_frame_save()` on the camera processor. The control loop copies/enqueues the latest frame; JPEG encoding and disk writing occur outside the main loop.

## Labels

Each successful enqueue appends one row to `<run>_labels.csv`:

```csv
photo,steering,throttle
photo_20260711_143005_123456.jpg,90,0.55
```

- `steering` is `state["steering_servo_deg"]`, rounded and clamped to logical `0..180` (`0` left, `90` center, `180` right).
- `throttle` is the forward part of `state["current_motor_pwm"]`, clamped to `0.0..1.0`. It is the absolute physical PWM label, so physical 55% is stored as `0.55`; reverse and zero are stored as `0.0`.

Appending CSV rows keeps per-frame label work bounded. When continuous capture is toggled off and again during shutdown, `finalize_photo_run()` converts the CSV into `<run>.json`, which the training pipeline can consume:

```json
{
  "photo_20260711_143005_123456.jpg": {
    "steering": 90,
    "throttle": 0.55
  }
}
```

The image and command are sampled from live software state at nearly the same capture request, but they are not hardware-synchronized measurements of wheel angle or motor torque. The steering value is the logical command, not servo feedback.

## Status and counts

`photo_status` changes through `CTRE`, `SAVE`, and `ERR` and is included in dashboard telemetry. Runtime counters track the current run and all photos, but the old dedicated `PRUN`/`PALL` dashboard pages were removed. Verify dataset size from the filesystem and label files rather than from a display page.

An empty run folder is removed during cleanup. A nonempty run remains on disk even if later validation finds a bad frame; dataset deletion is a separate, explicit decision.

## Failure behavior

If the camera has no frame to enqueue or a write cannot be queued, capture returns false and sets `photo_status` to `ERR`. The drive loop continues. Before training or publishing, run the frame decoder and label audit because a successful enqueue does not by itself prove that every JPEG was written and decodes correctly.

## Evidence

- `take_photo()`, `append_photo_run_row()`, `finalize_photo_run()`, and `update_auto_photo()` in `code/controller/current/rc_car_app/runtime.py`
- `PHOTO_BUTTON`, `AUTO_PHOTO_BUTTON`, and `PHOTO_RUN_CAPTURE_FPS` in `code/controller/current/rc_car_app/config.py`

## Related pages

- [Image Quality Checks](../data-governance/data-quality/image-quality-checks.md)
- [Dataset Overview](../data/dataset-overview.md)
- [Runtime Loop](runtime-loop.md)
