# Raw BGR Path

Raw BGR Path documents the default preprocessing that turns a captured camera frame
into the tensor fed to a SidewalkPilot steering checkpoint. It is the standard path
for every model version except the two that opt into CLAHE. The code lives in
`preprocess_steering_frame()` in `code/controller/current/rc_car_app/vision.py`.

## How it works

Once the capture thread has a BGR frame (the camera is configured as `BGR888`, so
no channel swap is needed), `preprocess_steering_frame(frame, model_choice)` runs
the following steps in order:

1. Check `steering_uses_clahe(model_choice)`. For the raw path this is `False`, so
   the frame is used **as-is** with no histogram equalization — no color conversion,
   no lighting normalization.
2. Resize to the model input size with area interpolation:
   `cv2.resize(frame, (STEERING_MODEL_WIDTH, STEERING_MODEL_HEIGHT))` where
   `STEERING_MODEL_WIDTH = 200` and `STEERING_MODEL_HEIGHT = 66`.
3. Cast to `float32` and scale to `[0, 1]` (`/ 255.0`).
4. Normalize to `[-1, 1]` with `(img - 0.5) / 0.5`.
5. Transpose from HWC to CHW (`np.transpose(img, (2, 0, 1))`).
6. Wrap as a torch tensor and add a batch dimension
   (`torch.from_numpy(...).float().unsqueeze(0)`).

| Field | Value |
|---|---|
| Owning file | `code/controller/current/rc_car_app/vision.py` |
| Entry function | `preprocess_steering_frame(frame, model_choice=None)` |
| Input format | BGR888 frame straight from the camera |
| Resize | 200 × 66, `cv2.INTER_AREA` |
| Normalization | `/255` then `(x - 0.5) / 0.5` → range `[-1, 1]` |
| Tensor layout | CHW, batch-of-1 |
| Applies to | every model version where `steering_uses_clahe()` is `False` |

The channel order is intentionally **not** converted to RGB. The training pipeline
and the runtime both keep BGR end to end, so the byte order the model sees at
inference matches the byte order it was trained on. In the resulting analysis dict,
`method` is tagged `SidewalkPilot:<version>:raw_bgr` so a log line proves which path
ran.

## Why this choice

Keeping the default path as plain resize-and-normalize BGR means the on-car
preprocessing is a faithful mirror of the training preprocessing, with the fewest
moving parts. Any lighting-robustness experiment (see the CLAHE page) becomes an
explicit per-version opt-in instead of a silent global change, which keeps model
comparisons honest. Skipping the extra HSV/CLAHE round-trip also keeps this path the
cheapest per frame, which matters on the Pi's CPU.

## Failure symptom

If BGR/RGB order were ever mismatched between training and this path, the model
would steer with a consistent color-driven bias rather than a hardware bias — worth
ruling out separately from the known drive-motor left drift. The `raw_bgr` vs
`clahe` tag in the analysis `method` string is the quickest way to confirm which
preprocessing actually ran for a given model version.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
