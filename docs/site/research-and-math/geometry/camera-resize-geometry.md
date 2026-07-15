# Camera Resize Geometry

Every steering model sees a small, fixed-size image, but the Raspberry Pi Camera Module 3 Wide captures a large one. Camera resize geometry is the deterministic step that maps the full camera frame down to the exact tensor shape a model was trained on. If the resize at inference time does not match the resize used in training, the model's learned geometry no longer lines up with the pixels it is given, so this is a correctness step, not just a convenience.

## How it works

The camera is configured in `vision.py` to `CAMERA_FRAME_WIDTH = 1280` × `CAMERA_FRAME_HEIGHT = 720` in BGR888. `CAMERA_FPS = 30` is a nominal constant; because the current Picamera2 configuration does not pass it as a control, the measured runtime FPS may differ. From there the model families resize differently:

**Series 1/2 (SteeringAutonomyV2, runs on the Raspberry Pi 5).** In `preprocess_steering_frame`:

```python
img = cv2.resize(frame, (STEERING_MODEL_WIDTH, STEERING_MODEL_HEIGHT),
                 interpolation=cv2.INTER_AREA)   # 200 x 66
img = img.astype(np.float32) / 255.0
img = (img - 0.5) / 0.5                          # normalize to [-1, 1]
img = np.transpose(img, (2, 0, 1))               # HWC -> CHW
```

- **Input:** a `720 × 1280 × 3` BGR frame (`H × W × C`).
- **Output:** a `1 × 3 × 66 × 200` float tensor in `[-1, 1]` (`STEERING_MODEL_WIDTH = 200`, `STEERING_MODEL_HEIGHT = 66`).

**Series 3 (SidewalkPilotV3, runs on Jetson Orin Nano).** The trainer's `resize_image_uint8` (in `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`) resizes to `320 × 180` with the same `cv2.INTER_AREA`, then converts to a tensor — so the Jetson Orin Nano pipeline must resize the Raspberry Pi 5's captured frame to `320 × 180` before inference to match training.

Two geometry details matter:

1. **Aspect ratio is not preserved.** `cv2.resize` maps the full frame onto the target box by independent x and y scale factors. 1280×720 (16:9) → 200×66 stretches the image vertically relative to its width, and → 320×180 (16:9) preserves it. This is fine *as long as inference uses the identical resize*, because the model learns the geometry of whatever shape it was trained on.
2. **`INTER_AREA` interpolation.** Both pipelines downscale with area interpolation, which is well suited to shrinking images because it aggregates source-pixel areas. The documentation does not claim that it eliminates all aliasing or is universally better than every alternative.

### Runtime use

- Series 1/2: `preprocess_steering_frame` in `code/controller/current/rc_car_app/vision.py`, called by `WebcamVisionProcessor._estimate_path_bias` before every inference. The model output (0–180° servo angle) is folded to a `[-1, 1]` heading bias.
- Series 3/4: trainer preprocessing and `jetson_inference_server.py` both use the canonical `320 × 180` geometry. The current Jetson Orin Nano runtime reproduces this resize before ONNX inference.

## Why this choice

- Fixing the input geometry makes preprocessing testable: the same stored frame and code path should yield the same tensor.
- `INTER_AREA` is a conventional downscaling choice and is used consistently in the current training and inference paths.
- Matching dimensions, interpolation, channel order, and normalization keeps deployment preprocessing aligned with training. It does not guarantee model accuracy.

## Worked example

Scaling `1280 × 720` down to the Series 1/2 `200 × 66`:

- Horizontal scale = `200 / 1280 = 0.15625`
- Vertical scale = `66 / 720 ≈ 0.0917`

Because the two factors differ, a pixel at source `(x, y) = (640, 360)` (frame center) maps to destination `(640·0.15625, 360·0.0917) ≈ (100, 33)` — the center of the 200×66 tensor, as expected. The unequal factors are exactly why aspect ratio is not preserved for the Series 1/2 shape, and why Series 3's 16:9 `320 × 180` keeps it.

## What could go wrong

- **Train/infer resize mismatch:** if inference resized to a different size, used a different interpolation, or preserved aspect ratio when training did not, the model would see geometry it never learned and steer wrong. The fix is to share the exact resize code/constants across both.
- **Wrong normalization pairing:** Series 1/2 expects `(img/255 - 0.5)/0.5` → `[-1, 1]`. Feeding `[0, 1]` (or forgetting the divide-by-255) would shift the input distribution and degrade steering silently.
- **Channel order / layout:** the pipeline keeps BGR (Picamera2 is configured `BGR888`) and transposes HWC→CHW. An accidental RGB swap or a missing transpose changes what the convolutions see.
- **Upscaling with `INTER_AREA`:** area interpolation is chosen for *downscaling*; the frames here are always shrunk, so this holds — but resizing a smaller crop *up* to the target would be a different regime and should use a different interpolant.

## Related pages

- `research-and-math/machine-learning/regression-framing.md`
- `ai-and-models/training-pipeline/overview.md`
- `autonomy-stack/camera-steering/overview.md`
