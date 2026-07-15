# Frame Capture

The first stage of the camera-steering pipeline: getting a live frame off the RPi Camera
Module 3 Wide and into memory so the rest of the pipeline can preprocess and run it.

## How it works

Capture is owned by `WebcamVisionProcessor` in
`code/controller/current/rc_car_app/vision.py`, backed by the `_PiCameraCapture` helper.
The camera is opened through **Picamera2** (`USE_PI_CAMERA = True`, `PI_CAMERA_NUM = 0`)
with a video configuration of `1280x720` in `BGR888` format. Requesting BGR directly is
deliberate: it keeps the frame in OpenCV's native channel order so the rest of the
pipeline never has to do an extra channel swap. The physical camera is mounted upside
down, so `PI_CAMERA_ROTATE_180 = True` applies a libcamera `Transform(hflip, vflip)` at
capture time rather than rotating in software later.

Capture runs in its own daemon thread (`_run`). The loop calls `capture.read()`, and on a
valid frame it runs the steering estimate, then stores the result and the raw frame under
a lock so the main control loop can read the latest steering bias without blocking on the
camera. It also tracks `camera_fps` from the inter-frame time. If a read fails it sleeps
50 ms and retries, so a momentary camera hiccup slows the loop instead of crashing it.

Because inference is decoupled from the driving loop, `runtime.py` doesn't wait on the
camera — it reads the *most recent* analysis via `get_analysis()`. That is also why
staleness matters: `apply_autonomous_controls()` treats a frame older than **0.75 s** as
stale and zeroes the steering bias rather than acting on an old view of the world.

## Why this choice

The current Camera Module 3 Wide integration is on the Pi, and all of the
81,237 Series 3/4 training images were captured through that path. Runtime preprocessing must match the
training capture geometry (same sensor, wide field of view, and 180-degree rotation) or the model
would see a different image distribution than it was trained on. Capturing in BGR and
flipping in hardware keeps the runtime frame identical to what the dataset pipeline saw.

## Constants used by this page

- `USE_PI_CAMERA = True`, `PI_CAMERA_NUM = 0`, `PI_CAMERA_ROTATE_180 = True` (`config.py`)
- Capture size `CAMERA_FRAME_WIDTH = 1280`, `CAMERA_FRAME_HEIGHT = 720`, `CAMERA_FPS = 30`,
  format `BGR888` (`vision.py`)
- Stale-frame threshold: `0.75 s` in `apply_autonomous_controls()` (`runtime.py`)

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
