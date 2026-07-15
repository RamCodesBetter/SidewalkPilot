# Output Scale

Output Scale documents how a SidewalkPilot steering checkpoint's raw network output
becomes a logical steering angle in degrees, and why the scale differs slightly
between Series 1 and Series 2. The math lives in the `SteeringAutonomyV2` head and in
`steering_output_scale_deg()` in
`code/controller/current/rc_car_app/vision.py`.

## How it works

`SteeringAutonomyV2` ends in a `Tanh()`, so the network's final layer produces a
value in `[-1, 1]`. The model's `forward()` maps that into a steering angle centered
on 90 degrees:

```python
def forward(self, x):
    x = self.backbone(x)
    return 90.0 + self.output_scale_deg * self.head(x)
```

With `tanh ∈ [-1, 1]`, the output angle spans `90 ± output_scale_deg`. The scale is
chosen per series:

```python
SERIES_1_STEERING_OUTPUT_SCALE_DEG = 86.0
SERIES_2_STEERING_OUTPUT_SCALE_DEG = 85.0

def steering_output_scale_deg(model_choice) -> float:
    return SERIES_2... if steering_model_series(model_choice) == 2 else SERIES_1...
```

`steering_model_series()` returns `2` when the version starts with `2.` and `1`
otherwise. So a Series 1 model can output roughly `4 … 176` degrees
(`90 ± 86`) and a Series 2 model roughly `5 … 175` degrees (`90 ± 85`). At inference
in `_estimate_path_bias()` the angle is hard-clamped to a valid range with
`torch.clamp(..., 0.0, 180.0)`, then converted to the normalized heading the control
loop consumes: `heading_bias = (steering_angle - 90.0) / 90.0`, clamped to
`[-1, 1]`.

| Field | Value |
|---|---|
| Owning file | `code/controller/current/rc_car_app/vision.py` |
| Final activation | `nn.Tanh()` → `[-1, 1]` |
| Angle formula | `90.0 + output_scale_deg * tanh(...)` |
| Series 1 scale | `SERIES_1_STEERING_OUTPUT_SCALE_DEG = 86.0` |
| Series 2 scale | `SERIES_2_STEERING_OUTPUT_SCALE_DEG = 85.0` |
| Series select | `steering_model_series()` (version starts with `2.` → Series 2) |
| Runtime clamp | `torch.clamp(angle, 0.0, 180.0)` |
| To heading | `(angle - 90.0) / 90.0`, clamped `[-1, 1]` |

The output is a **logical** steering angle on the project's 0=left / 90=center /
180=right convention. Servo-specific compensation (trim, hysteresis) is applied later
in the hardware mapping layer, not here — the model and its output stay in clean
logical degrees.

## Why this choice

Anchoring at 90 with a symmetric `tanh` scale gives a naturally centered output: a
zero-confidence or straight prediction lands on 90 (center) instead of drifting to an
edge. Baking the scale into `forward()` (rather than post-processing) means the model
returns a ready-to-use logical angle. The small Series 1 vs Series 2 difference
(86.0 vs 85.0) matches how each series' labels were scaled during training, so the
angle range at inference mirrors the range the network was trained to produce — the
scale is picked automatically from the version string via `steering_output_scale_deg()`.

## Failure symptom

If a Series 2 model were loaded with the Series 1 scale (or vice-versa), the steering
range would be off by one degree at the extremes — small, but it means the wrong
constant is in play. `_load_steering_model()` sets the scale from the version, so a
mismatch usually points at a wrong `model_choice` string rather than the checkpoint
itself. The runtime clamp to `0–180` guards against any raw output escaping the
valid servo range.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
