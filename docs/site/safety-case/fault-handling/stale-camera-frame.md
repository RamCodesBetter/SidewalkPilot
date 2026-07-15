# Stale Camera Frame

The camera model is the only thing steering the car in autonomous mode. If the camera
frame stops updating (Picamera2 hiccup, thread stall) the model would keep steering on
a frozen image. SidewalkPilot treats a stale frame as a stop condition, not something
to steer through.

## Hazard

In autonomous mode, steering comes from the camera model's analysis of the latest
frame. A frozen or missing frame means the steering command no longer reflects the
world ahead. Continuing to steer on it could run the car off the sidewalk.

## Detection

In `apply_autonomous_controls()` (`runtime.py`), local Raspberry Pi 5 analysis carries the timestamp
of the frame it was computed from. That local frame is judged stale when:

```
model_frame_is_stale = time.time() - last_frame_time > 0.75   # seconds
```

When stale, the local analysis is blanked (`heading_bias = 0`, `confidence = 0`, no
edges) and tagged `method = "stale_model_frame"`.

The live Series 3/4 path adds a separate Jetson Orin Nano cache-age check. The Raspberry Pi 5 accepts only a
result for the selected model that is no more than `JETSON_RESULT_MAX_AGE_SEC = 0.25`
seconds old. If no matching fresh sample exists, the method becomes
`jetson_unreachable`, confidence remains zero, and the same stop path is used.

## Response

A stale frame or Jetson Orin Nano result is treated the same as no model / low confidence: the car does not
guess a steering angle. `apply_hard_stop_state()` is called (via the confidence
branch, since stale forces `confidence = 0 < LOW_CAMERA_CONFIDENCE = 0.25`), which
centers steering, zeroes throttle, sets brake force to `1.0`, and sets
`stop_reason = "model_low_confidence"`. The car holds until fresh, confident frames
resume or the operator takes over.

## Stop condition and who triggers it

Automatic, evaluated every autonomous tick. Local Raspberry Pi 5 analysis uses the 0.75-second
frame threshold; the live Jetson Orin Nano result uses the 0.25-second matching-sample threshold.
The operator can override at any time; the model cannot resume driving until its result
is fresh again.

## Evidence

- Code: `runtime.py` — `apply_autonomous_controls` (the local `0.75` stale test,
  `jetson_client.get_latest_sample(...)`, and `apply_hard_stop_state`).
- Config: `config.py` — `JETSON_RESULT_MAX_AGE_SEC = 0.25`,
  `LOW_CAMERA_CONFIDENCE = 0.25`, and `HIGH_CAMERA_CONFIDENCE = 0.60`.
- Vision: `vision.py` — `WebcamVisionProcessor` updates `last_frame_time` per frame.
- Field evidence: a forced stale-frame stop clip is **planned / not-yet-captured**.

## Series 3/4 note

Series 3/4 send the newest frame to the Jetson Orin Nano through `AsyncJetsonSteeringClient`.
Network and inference waits run in that worker rather than in the 60 Hz controller
loop. The controller consumes only the newest cached, model-matching result and requests
a hard stop when that result is unavailable or older than 0.25 seconds. This behavior is
implemented and covered by async-client tests; a formal worst-case timing measurement is
still not claimed.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
