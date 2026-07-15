# Shadow Failures

Shadow failures are the single most stubborn perception problem on SidewalkPilot. In bright sun, a tree trunk, a fence, or a parked car throws a hard-edged shadow straight across the concrete. That shadow edge looks, to the model, almost exactly like the boundary between sidewalk and grass — a long, high-contrast, roughly-vertical line running up the frame. The car steers to "follow" it and drifts off the true path.

## What goes wrong

In recorded operator observations, some earlier models held open concrete and then drifted near a sharp diagonal shadow. That pattern is consistent with visual feature confusion, but the existing record does not isolate perception from labels, mechanics, timing, or closed-loop recovery as the sole cause.

## Suspected cause

The classic fallback estimator in `code/controller/current/rc_car_app/vision.py` illustrates one possible mechanism: `estimate_path_bias_from_frame` builds a neutral-gray, low-color-spread, lit mask (`chroma < 18`, `bgr_spread < 55`, `gray > 45`). A hard shadow can remove concrete pixels from that mask. The current Series 3/4 path uses the Jetson Orin Nano neural result rather than that heuristic, so this example does not prove what the neural model learned.

The field observation is a **turn-vs-shadow tradeoff**: some turn-eager checkpoints also chased shadow edges, while more center-biased behavior could miss turns. Targeted real turn-in-shadow footage is the most direct next data experiment. The existing evidence does not prove that augmentation can never solve the problem or that one collection run guarantees a fix.

## What I changed / plan to change

- **Synthetic shadow augmentation** is implemented in the Series 3 trainer. Earlier notes called one version too soft, but no preserved augmentation-only ablation proves that diagnosis.
- **Current field result:** v3.4 completed every harsh-shadow case presented in the July 13 comparison and became the selected baseline. That is evidence for those cases, not a universal shadow-robustness claim. Future collection is triggered by preserved failures rather than a fixed frame-count promise.
- Runtime temporal smoothing (~0.45) on the Series 3 output damps single-frame shadow flips; note this is a runtime smoothing value, not a training-time weight EMA.

## Test setup

- **Setup:** Raspberry Pi 5 controller, Raspberry Pi Camera Module 3 Wide, bright direct sun; branch `lidar-aeb-v2`.
- **Procedure:** drive a known sidewalk stretch that has a strong diagonal tree/fence shadow; run `car`, then select `<version>` on the dashboard model page.
- **Pass/warn/fail:** pass = holds true edge through the shadow; warn = visible wobble but recovers; fail = tracks the shadow and needs manual takeover.
- **Evidence to attach (planned):** runtime CSV log, on-sidewalk video of the shadow stretch, manual-takeover count, model version.

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
