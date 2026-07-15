# Raw BGR vs. CLAHE

This page records the decision to feed the model a **raw BGR frame** (only
resized and normalized) rather than applying CLAHE contrast equalization at
inference — a preprocessing choice that must match exactly between training and
the car.

## Decision

The runtime preprocessing (`preprocess_steering_frame` in
`code/controller/current/rc_car_app/vision.py`) is deliberately minimal:

```python
img = cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)
img = img.astype(np.float32) / 255.0
img = (img - 0.5) / 0.5          # normalize to [-1, 1]
img = np.transpose(img, (2, 0, 1))
```

The camera is captured directly in OpenCV **BGR888** (`_PiCameraCapture`), and no
channel swap is done — the frame stays BGR end to end. **CLAHE is applied for
exactly two legacy model choices** (`2.0`, `2.0b`) via `steering_uses_clahe(...)`
/ `apply_clahe_to_bgr(...)`; every other model, including all of Series 3, runs
**raw BGR**. The Series 3 model cards state the input plainly:
`BGR -> resize 320x180 -> normalize (x/255 - 0.5)/0.5` (no CLAHE/HSV).

The key rule is **train/serve parity**: whatever preprocessing a checkpoint was
trained with must be reproduced byte-for-byte at inference, which is why the
CLAHE flag is keyed to specific model versions and the fallback path is labelled
`raw_bgr` vs `clahe` so the runtime can't silently mismatch.

## Why raw BGR (mostly)

CLAHE (Contrast Limited Adaptive Histogram Equalization) locally boosts contrast
and can make edges pop in flat lighting — which is why it was tried for the `2.0`
models. But it has real costs:

- It **changes the pixel statistics** the network sees, so it *must* be applied
  identically at train and inference or the model silently degrades. That's one
  more place to get out of sync between the trainer, the Raspberry Pi 5, and Jetson Orin Nano.
- On tree-dappled / hard shadows it can *amplify* the very light/dark patches
  that already confuse the model, sharpening the distractor instead of the
  sidewalk edge.
- It costs CPU per frame in a real-time loop.

The Series 3 answer was to keep inference preprocessing dead simple (raw BGR) and
instead make the model robust to lighting through **training-time augmentation**
(synthetic shadows, brightness/contrast jitter, etc.) rather than a fixed
inference-time transform. See the augmentation-vs-fixed-preprocessing decision.

## Alternatives considered

| Option | Pros | Cons |
|---|---|---|
| CLAHE at inference (used only by `2.0`/`2.0b`) | pops edges in flat light | must match training exactly; amplifies dappled-shadow distractors; per-frame CPU |
| Convert BGR→RGB before the net | matches many pretrained backbones | an extra swap and a parity trap for a custom net trained on BGR |
| **Raw BGR, resize + normalize only (chosen, Series 3)** | trivial, fast, one obvious parity contract; robustness pushed to training aug | no inference-time contrast help — relies on augmentation to handle lighting |

## How to know it worked (test gate)

- The chosen checkpoint's card / training config and the runtime must agree on
  BGR + resize + `(x/255 - 0.5)/0.5` and on whether CLAHE is on. Series 3 = off.
- The fallback method string is tagged `SidewalkPilot:<version>:raw_bgr` (or
  `:clahe`) so a mismatch is visible in the logs.
- Compare CLAHE vs raw on the same hard-shadow clips: bench comparison images
  live under `code/test_files/` (`hsv_clahe_comparisons/`).

## Related pages

- `engineering-process/design-decisions/augmentation-vs-fixed-preprocessing.md`
- `testing/failures/overview.md`
- `roadmap/next-steps.md`
