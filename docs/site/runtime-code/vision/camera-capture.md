# Vision Runtime

Camera Capture covers how the runtime opens the Raspberry Pi Camera Module 3 Wide, pulls
frames, and hands them to the steering estimator. All of this lives in
`code/controller/current/rc_car_app/vision.py`, inside the `_PiCameraCapture`
helper and the `WebcamVisionProcessor` capture thread.

## How it works

Capture is gated by two flags in `config.py`: `ENABLE_WEBCAM_VISION = True` and
`USE_PI_CAMERA = True`. When both are set, `WebcamVisionProcessor._open_capture()`
builds a `_PiCameraCapture(PI_CAMERA_NUM)` (camera index `0`) and calls `.open()`.

`_PiCameraCapture.open()` constructs a `Picamera2` object and configures a video
stream with these exact parameters (all constants in `vision.py`):

| Field | Value |
|---|---|
| Owning file | `code/controller/current/rc_car_app/vision.py` |
| Capture backend | Picamera2 (`from picamera2 import Picamera2`) |
| Camera index | `PI_CAMERA_NUM = 0` (from `config.py`) |
| Frame size | `CAMERA_FRAME_WIDTH` × `CAMERA_FRAME_HEIGHT` = 1280 × 720 |
| Pixel format | `BGR888` (kept in OpenCV BGR order on purpose) |
| Nominal FPS constant | `CAMERA_FPS = 30`; actual rate is measured because this value is not currently passed into the Picamera2 configuration |
| Rotation | `PI_CAMERA_ROTATE_180 = True` → `Transform(hflip=True, vflip=True)` |

The 180-degree rotation is applied through libcamera's `Transform` because the
camera is mounted upside down on the chassis. `hflip` and `vflip` are both tied to
the single `PI_CAMERA_ROTATE_180` flag, so a 180-degree flip is done as a combined
horizontal + vertical mirror.

Frames are read on a dedicated daemon thread (`WebcamVisionProcessor._run`), not on
the main control loop. Each iteration calls `capture.read()`, which returns
`(ok, frame)` from `Picamera2.capture_array()`. On a good read the frame is fed to
`_estimate_path_bias`, the resulting analysis is stored under a lock, the latest raw
frame is cached for preview/photo/dashboard use, and a rolling `camera_fps` is
computed from the inter-frame delta. A failed read sleeps 50 ms before retrying instead of
using a tight retry loop.

The size, format, and transform are explicit camera-configuration inputs. The declared
`CAMERA_FPS` value is not currently supplied as a Picamera2 control, so it must not be
reported as a guaranteed capture rate; the dashboard/CSV measurement is authoritative for
a particular run.

## Why this choice

The frame is deliberately kept in **BGR888** so the rest of the pipeline (the model
preprocessing, the LAB/edge fallback analysis, the dashboard RGB565 encoder, and
`cv2.imwrite` for training photos) uses a defined channel order. The controller loop reads
cached analysis instead of directly calling `capture_array()`, reducing coupling to camera
latency. This is a concurrency design, not a formal guarantee that Python scheduling or a
process-wide camera fault can never affect loop timing.

## Failure symptom

If Picamera2 is unavailable or the camera fails to start, `start()` prints
`Failed to open Raspberry Pi Camera for vision processing: ...` (or `Raspberry Pi 5 camera vision
processor started.` on success) and returns `False`, leaving no active camera processor. If
autonomy is requested without a fresh accepted model result, the autonomous path requests a
hard stop. A camera that opens but never produces frames leaves
`last_frame_time` at `0.0` and `camera_fps` at `0.0`; downstream the analysis stays
at the empty default (`heading_bias = 0`, `confidence = 0`), and the CSV log's
camera columns read as centered/zero.

## Preprocessing Contracts

Series 1/2 images resize to `200x66`; Series 3/4 images resize to `320x180`. Frames remain BGR to match training, convert to `float32`, normalize to `[-1, 1]`, transpose HWC to CHW, and add a batch dimension. Only v2.0 and v2.0b opt into the historical CLAHE preprocessing path; every other registered model uses raw BGR preprocessing.

Series 1 direct-regression output uses approximately `90 +/- 86` degrees and Series 2 uses `90 +/- 85`, followed by a `0..180` clamp. Series 3/4 decoding chooses a steering class and local offset. Physical steering trim is applied later by the hardware mapping and is not baked into model output.

## Model Selection and Jetson Orin Nano

The registered list contains Series 1/2 PyTorch checkpoints and Series 3/4 ONNX names. In camera-only mode, the Raspberry Pi 5 records the requested name and sends it with frames; the Jetson Orin Nano must confirm loading and return a fresh matching result. Series 4 PC/PCF history resets on model changes. A dashboard name alone does not prove the artifact loaded successfully.

Inference uses latest-frame semantics. Old pending frames are replaced, and Raspberry Pi 5 autonomy rejects Jetson Orin Nano results older than the configured freshness limit.

## Related pages

- [Runtime Loop](../runtime-loop.md)
- [Model Inference](../../autonomy-stack/camera-steering/model-inference.md)
- [Bench Tests](../../testing/bench-tests/overview.md)
