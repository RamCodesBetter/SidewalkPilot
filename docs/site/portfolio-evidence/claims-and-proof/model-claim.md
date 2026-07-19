# Model Claim

## Defensible Field Claim

SidewalkPilot v3.4 steered the physical project car through the normal turns and harsh-shadow cases presented in the July 13, 2026 comparison, and it performed better in that run than v3.4b, v3.3, and v3.3b.

A later supervised Series 4 comparison found `4.0f` usable and approximately tied with v3.4 across the cases presented: each passed two cases that the other failed. The four 4.0 models that consumed steering history repeatedly held earlier predictions and were not usable enough for promotion.

These claims are bounded to those comparisons. They do not establish performance on every sidewalk, route, shadow, weather condition, or obstacle.

## Defensible Offline Claim

The common evaluator measures every checkpoint on one frozen 6,952-frame challenge set. Several 4.0 PC/PCF models score above v3.4 offline, but their physical steering-echo failure shows that high open-loop metrics do not guarantee stable closed-loop driving. The 4.1 experiments were trained specifically to test corrections for that failure and have no field verdict yet.

## Evidence

| Evidence | Result |
|---|---|
| Common evaluator | architecture-specific preprocessing and decoding on the same images and labels |
| July 13 physical comparison | v3.4 completed every shadow case presented and ranked first among v3.3-v3.4b |
| 4.0 supervised comparison | `4.0f` viable with complementary outcomes versus v3.4 |
| 4.0 history-model behavior | `4.0p/r/a/c` repeated earlier steering predictions and were rejected |
| 4.1 training | six corrected experiment checkpoints trained and exported; runtime and field validation pending |

## Model Contracts

v3.4:

- Input `[N,3,180,320]` normalized BGR.
- Output `[N,19]`: nine steering logits, nine local offsets, and one unused throttle value.
- Public model: [SidewalkPilot-v3.4](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.4).

Series 4:

- PC input: image plus `[N,3]` prior steering targets; output `[N,1,18]`.
- CF input: image only; output `[N,4,18]`.
- PCF input: image plus prior steering targets; output `[N,4,18]`.
- Horizon 0 supplies the current steering prediction; future horizons are training outputs, not future inputs.
- Series 4 does not predict throttle.

## Limitations

- The field comparisons were supervised and qualitative rather than formal route-controlled benchmarks.
- Exact environmental measurements and a complete per-case score sheet were not preserved.
- 4.1 has not been integrated into the live selector or tested on the car.
- Steering success does not validate LiDAR, GPS, dashboard, or pedestrian behavior.
- The model is one component in a supervised system, not an independent safety mechanism.

See the [Series 3 table](../../ai-and-models/model-zoo/series-3.md), [Series 4 table](../../ai-and-models/model-zoo/series-4.md), and [evaluation PDF](../../steering_model_report.pdf).
