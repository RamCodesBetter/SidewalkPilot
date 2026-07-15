# CLAHE Path

CLAHE Path documents the optional lighting-normalization preprocessing that a
specific pair of steering checkpoints opts into before inference. It sits inside the
same `preprocess_steering_frame()` used by the raw path, in
`code/controller/current/rc_car_app/vision.py`.

## How it works

Whether a frame gets CLAHE is decided per model version by `steering_uses_clahe()`:

```python
def steering_uses_clahe(model_choice) -> bool:
    choice = str(model_choice or DEFAULT_STEERING_MODEL_CHOICE).strip().lower()
    return choice in {"2.0", "2.0b"}
```

So **only versions `2.0` and `2.0b`** take the CLAHE path; every other version uses
the raw BGR path. When enabled, `preprocess_steering_frame()` calls
`apply_clahe_to_bgr(frame)` before the shared resize/normalize steps. That helper:

1. Converts the BGR frame to HSV (`cv2.COLOR_BGR2HSV`).
2. Splits H, S, V and applies CLAHE only to the **V (brightness) channel** with
   `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))`.
3. Merges the enhanced V back with the original H and S and converts back to BGR
   (`cv2.COLOR_HSV2BGR`).

The equalized frame then flows through the exact same downstream steps as the raw
path: resize to 200 × 66 (`STEERING_MODEL_WIDTH` × `STEERING_MODEL_HEIGHT`),
`/255`, `(x - 0.5) / 0.5`, HWC→CHW, batch-of-1 tensor.

| Field | Value |
|---|---|
| Owning file | `code/controller/current/rc_car_app/vision.py` |
| Gate function | `steering_uses_clahe(model_choice)` |
| Enabled for | `2.0`, `2.0b` only |
| Helper | `apply_clahe_to_bgr(frame)` |
| Algorithm | CLAHE on the HSV **V** channel, `clipLimit=2.0`, `tileGridSize=(8, 8)` |
| Method tag | `SidewalkPilot:<version>:clahe` |

## Why this choice

CLAHE (Contrast Limited Adaptive Histogram Equalization) locally boosts contrast so
shadowed sidewalk and bright pavement look more alike, which was an attempt to make
steering more robust to harsh lighting. Equalizing only the V channel preserves hue
and saturation so colors are not distorted — just brightness contrast. It is gated
to exactly the versions trained with matching preprocessing, so a model only ever
sees the pixel distribution it was trained on. Newer shadow-robustness work (Series
2/3) is being addressed with real hard-shadow training data and augmentation rather
than by expanding this runtime CLAHE gate.

## Failure symptom

The one real risk is a train/inference mismatch: running CLAHE for a version that
was trained without it (or vice-versa) would degrade steering for that version only.
The `method` tag in the analysis dict (`...:clahe` vs `...:raw_bgr`) is the
definitive check of which preprocessing actually ran, so verify it against the
version before drawing conclusions from a field run.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
