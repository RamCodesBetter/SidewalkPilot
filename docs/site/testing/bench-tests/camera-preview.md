# Camera Preview

The camera-preview bench test puts the live camera feed on screen with the model's read of it overlaid, so I can confirm the RPi Camera Module 3 Wide is capturing correctly, framed right, and feeding the vision pipeline before I collect training photos or trust autonomy. It runs `code/test_files/camera/test_camera_preview.py`.

## How it works

- It starts the same `WebcamVisionProcessor` the runtime uses (via Picamera2) and pulls preview frames from its cache, checking the same capture path before network encoding and remote inference.
- It draws each frame into a `640x360` pygame window and overlays a status bar with the analysis `method`, the model `confidence`, and the frame `age` in seconds, plus an `ESC to quit` hint. If no frame is available yet it shows `Waiting for camera frame...`.
- Because it reuses the runtime vision processor, a clean preview checks capture, orientation, and local frame handling. It does not by itself verify Jon connectivity, the selected ONNX artifact, or physical steering.

## Command

Run on the Pi 5 (needs a display or forwarded X session):

```bash
python3 code/test_files/camera/test_camera_preview.py
# ESC to quit
```

Related camera utilities are `code/test_files/camera/test_camera_flip.py` for orientation and `code/test_files/camera/sidewalk_image_test.py` for still-image checks.

## Pass / warn / fail

- Pass: a live, correctly-oriented, correctly-exposed feed; the status bar updates and frame `age` stays small (fresh frames).
- Warn: frame `age` climbing or exposure/white-balance off — a capture-rate or lighting problem to note before a data run.
- Fail: `Failed to start webcam vision processor` or a stuck `Waiting for camera frame...` — fix the camera before anything downstream.

## Why it matters

- The 81,237 Series 3/4 images were captured through this Pi camera path, so framing, exposure, and orientation directly affect data quality. A preview is a low-cost pre-collection check, not proof that those properties stay fixed for the full run.
- Sharing the runtime's vision processor means the preview doubles as a quick check that the model's input path is healthy, not just the raw camera.

## Evidence to attach

- A screenshot of the preview with the status bar
- Note of frame `age` under load
- Any framing/exposure issues found

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
