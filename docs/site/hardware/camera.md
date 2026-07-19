# Camera

The camera is the primary sensor for SidewalkPilot: it feeds the steering model and
it is the source of the current 81,237-image real Series 3/4 dataset. It is a Raspberry Pi Camera Module 3 Wide
connected to the Raspberry Pi 5 over the CSI ribbon and driven through Picamera2 in
`code/controller/current/rc_car_app/vision.py`.

## Parts (Amazon)

- [Raspberry Pi Camera Module 3 Wide](https://www.amazon.com/Raspberry-Pi-Camera-Module-Wide/dp/B0BRY757NX?ref_=ast_sto_dp&th=1) — $69.99

## How It Works

- `vision.py` opens the module with `Picamera2(camera_num=PI_CAMERA_NUM)` and configures a
  `1280x720` (`CAMERA_FRAME_WIDTH` x `CAMERA_FRAME_HEIGHT`) `BGR888` video stream.
  `CAMERA_FPS = 30` records the nominal target, but the current Picamera2 configuration
  does not explicitly pass a frame-rate control; runtime `camera_fps` is the measured value.
- The current camera mount requires a 180-degree correction, so `PI_CAMERA_ROTATE_180 = True`
  applies a `Transform(hflip=True, vflip=True)` in the capture configuration to give an
  upright frame.
- Each captured frame is resized before inference. Series 1/2 preprocessing resizes to
  `200x66`; Series 3/4 use a `320x180` input on the Jetson Orin Nano. Operator-enabled capture saves
  selected frames under `media/photos/` for dataset preparation.
- If Picamera2 is unavailable, the vision processor has no live frame. Manual operation can
  continue, while the autonomous path treats the model result as unavailable.

## Why This Choice

- The Module 3 **Wide** was selected to retain more sidewalk context near the image edges
  during turns. This project has not preserved a controlled wide-versus-standard comparison.
- The module is integrated through the Raspberry Pi 5 camera path, and the current 81,237-image Series 3/4 dataset was captured
  with it. Keeping the same camera avoids one source of sensor-domain shift, although
  lighting, exposure, mounting, route, and weather can still change the image distribution.

## Verify Before a Run

- Bench tests: `code/test_files/camera/test_camera_preview.py` (live preview) and
  `code/test_files/camera/test_camera_flip.py` (confirm the 180 rotation is correct).
- A black or frozen preview can come from the ribbon, camera selection, device ownership,
  configuration, or driver state. An upside-down image indicates the configured transform
  does not match the physical mount.

## Related Pages

- [Hardware Build Overview](build-overview.md)
- [Bench Tests](../testing/bench-tests/overview.md)
- [Hardware Class](../runtime-code/hardware/hardware-class.md)
