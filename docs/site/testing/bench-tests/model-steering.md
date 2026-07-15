# Model Steering

The model-steering bench test closes the loop between the camera and the wheels with the drive motors off, so I can watch the model turn the front wheels in response to the camera before allowing vehicle motion. These utilities live under `code/test_files/steering/`.

## How it works

There are a few layered utilities:

- `steering/model_steering_test.py` loads a model via `WebcamVisionProcessor(model_choice=...)`, starts the camera, and in a loop reads the analysis, clamps the predicted `steering_angle_deg` to `0..180`, and writes it to the steering servo while forcing drive-motor outputs to zero. Run `--help` for the flags supported by the checked-out version.
- `steering/model_or_fallback_steering_test.py` is the trimmed variant with just `--model` and `--no-servo`; it exercises the same vision path and the model-or-fallback logic without the dashboard sender.
- `steering/autonomous_steering_test.py` is the broader autonomy-path variant.

Series 1/2 can run through the Pi-local path. Series 3/4 use the Jetson inference link in the live architecture, so a full bench test also verifies that Ethernet service and model selection.

## Command

Run on the Pi 5, wheels off the ground, motors stay OFF the whole test:

```bash
# move the servo from model predictions (drive motors forced off):
python3 code/test_files/steering/model_steering_test.py --model 2.4b

# only print predicted servo degrees, don't move anything:
python3 code/test_files/steering/model_steering_test.py --model 2.4b --no-servo
```

## Pass / warn / fail

- Pass: pointing the camera left/right/straight makes the wheels follow with the expected sign (`0=left`, `90=center`, `180=right`); `method` shows `SidewalkPilot:` and confidence is reasonable.
- Warn: predictions lag (large frame `age`) or the model collapses to straight on obvious turns — a model/data issue, logged for the next version, not a wiring bug.
- Fail: camera won't start, or predictions are frozen — fix the vision path before reading any steering behavior.

## Why it matters

- It is the honest, no-motion way to validate a new model or a new fallback before a real drive; it also cross-checks the runtime's clamp and the `0..180` logical convention.
- The `SRVO` dashboard mirror lets me confirm the same value is threaded through the telemetry serializer, not just the servo.
- Field context: MAE alone can hide straight collapse, so use turn capability and confusion balance before field testing. The bench test itself cannot promote a model; v3.3/v3.3b passed offline review but later regressed on the car.

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
