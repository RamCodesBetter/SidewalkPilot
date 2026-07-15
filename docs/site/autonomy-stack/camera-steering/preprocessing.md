# Preprocessing

The stage between a raw captured frame and the model input tensor: resize, normalize,
reorder channels, and (for some models) enhance contrast.

## How it works

Preprocessing for the on-Pi Series 1/2 path lives in `preprocess_steering_frame()` in
`code/controller/current/rc_car_app/vision.py`. Given a captured BGR frame it:

1. Optionally applies CLAHE contrast enhancement (see below).
2. Resizes to the model input size using `cv2.INTER_AREA`.
3. Scales pixels to `[0, 1]` (`/ 255.0`), then normalizes to `[-1, 1]` with `(x - 0.5) / 0.5`.
4. Transposes from `HxWxC` to `CxHxW` and wraps it as a `float32` torch tensor with a
   leading batch dimension.

The input size differs by series, and this is a hard fact from the code:

- **Series 1/2** (`SteeringAutonomyV2`) uses `STEERING_MODEL_WIDTH = 200`,
  `STEERING_MODEL_HEIGHT = 66` — a NVIDIA-PilotNet-style small input that keeps inference
  cheap enough to run on the Pi.
- **Series 3** (`SidewalkPilotV3`) is trained at **320x180** (see `preprocess_image()` /
  `resize_image_uint8()` in the Series 3 trainer). Because Series 3 runs on the Jetson,
  the Pi's job for that path is to hand off a preprocessed frame; see
  `jetson-inference-link.md`.

CLAHE (Contrast Limited Adaptive Histogram Equalization, `clipLimit=2.0`,
`tileGridSize=(8,8)`, applied to the V channel in HSV) is **only** enabled for model
choices `2.0` and `2.0b` via `steering_uses_clahe()`. Every other Series 1/2 checkpoint
sees the raw BGR frame. The active preprocessing is reported in the analysis `method`
string as `clahe` or `raw_bgr`, so the dashboard/logs show which path ran.

## Why this choice

The normalization (`[-1, 1]`) and channel order must match training exactly, or the model
sees an out-of-distribution image and steers badly. Keeping the frame in BGR from capture
through preprocessing avoids an accidental R/B swap — a classic silent bug that would flip
the model's color world. `INTER_AREA` is the right resampler for shrinking, which is what
every resize here does (1280x720 down to 200x66 or 320x180).

## Constants used by this page

- `STEERING_MODEL_WIDTH = 200`, `STEERING_MODEL_HEIGHT = 66` (Series 1/2, `vision.py`)
- Series 3 input `320x180` (`sidewalkpilot_trainer.py`)
- Normalization `(x/255 - 0.5) / 0.5`; CLAHE only on `2.0` / `2.0b` (`vision.py`)

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
