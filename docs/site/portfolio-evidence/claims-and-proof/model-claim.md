# Model Claim

## Defensible Claim

SidewalkPilot v3.4 can steer the physical project car through the normal turns and harsh-shadow cases presented in the July 13, 2026 comparison, and it performed better in that run than v3.4b, v3.3, and v3.3b.

This is a bounded field claim. It is not a claim that v3.4 handles every sidewalk, shadow, route, or weather condition.

## Evidence

| Evidence | Result |
|---|---|
| 81,237-image Series 3 evaluation | v3.4: Bal9 33.3%, turn exact 32.6%, turn +/-1 60.7%, straight exact 65.5%, MAE 14.377 degrees, signed error +0.799 degrees |
| Same evaluation, v3.4b | Lower MAE at 13.904 degrees but weaker Bal9 and turn scores than v3.4 |
| July 13 physical comparison | v3.4 completed every shadow case presented and ranked first |
| Comparison result | v3.4b slightly worse; v3.3 worse than v3.2; v3.3b much worse than v3.2b |

The result demonstrates why the project does not rank models by MAE alone. The dataset contains many straight frames. A model can reduce average error by favoring straight predictions while losing the turns needed to stay on the sidewalk.

## Artifact Contract

- Model artifact: `code/ai_models/SidewalkPilot-v3.4.onnx`.
- Public repository: [SidewalkPilot-v3.4](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.4).
- Input: normalized BGR tensor, shape `[N, 3, 180, 320]`.
- Output: 19 values per sample: nine steering logits, nine local offsets, and one throttle value.
- Decoder: `code/controller/current/rc_car_app/vision.py`.
- Runtime selection: `--model 3.4` or the current default list selection.

## Why v3.3 Matters To The Story

v3.3 and v3.3b were intended to harden the model against shadows. Their physical regression is valuable evidence: increasing the strength of a plausible augmentation did not automatically improve robustness. The change likely damaged or obscured visual structure the model needed for turns. v3.4 represented a correction rather than a simple continuation.

## Limitations

- The July 13 record is qualitative and operator-reported.
- Exact route, lighting measurements, weather, duration, takeover count, and video IDs were not saved.
- The result applies to the conditions presented, not arbitrary sidewalks.
- Steering success does not validate LiDAR, GPS, dashboard, or pedestrian behavior.
- The model is one component in a supervised system, not an independent safety mechanism.

The fastest technical verification is to inspect the [Series 3 comparison](../../ai-and-models/model-zoo/series-3.md), the evaluation PDF, the ONNX card, and the runtime decoder together.
