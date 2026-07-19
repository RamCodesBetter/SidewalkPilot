# Model Claim

## Defensible Field Claim

SidewalkPilot v3.4 steered the physical project car through the normal turns and harsh-shadow cases presented in the July 13, 2026 comparison, and it performed better in that run than v3.4b, v3.3, and v3.3b.

This is bounded to that supervised comparison. It is not a claim that v3.4 handles every sidewalk, route, shadow, weather condition, or obstacle.

## Defensible Offline Claim

On a common 6,952-frame frozen Series 3/4 challenge subset, the first Series 4 PC and PCF models outperform v3.4 on Bal9, turn exact, turn +/-1, and MAE. `4.0p` is the leading class-balanced candidate; `4.0c` has the lowest MAE. These models are trained and runtime-supported but not field-validated.

## Evidence

| Evidence | Result |
|---|---|
| Common evaluator | all 46 checkpoints use the same images and labels |
| v3.4 | Bal9 24.2%, turn exact 22.6%, turn +/-1 56.2%, MAE 15.083 degrees |
| v3.4b | lower MAE 13.985, but weaker turn metrics and worse field result |
| `4.0p` | Bal9 34.5%, turn exact 32.1%, turn +/-1 65.9%, MAE 12.396 |
| `4.0c` | Bal9 32.0%, turn exact 29.4%, MAE 11.321 |
| July 13 physical comparison | v3.4 completed every shadow case presented and ranked first |

## Artifact Contracts

v3.4:

- Input `[N,3,180,320]` normalized BGR;
- Output `[N,19]`: nine steering logits, nine local offsets, one unused learned-throttle value;
- Public model: [SidewalkPilot-v3.4](https://huggingface.co/ram-shreyas-naik-sabavat/SidewalkPilot-v3.4).

Series 4:

- PC input image + `[N,3]` target history, output `[N,1,18]`;
- CF input image, output `[N,4,18]`;
- PCF input image + history, output `[N,4,18]`;
- Horizon 0 commands steering; no learned throttle;
- Artifacts exist locally but public v4 model repositories have not been released.

## Why This Is an Engineering Result

The useful result is not “the newest model has the smallest number.” It is that controlled temporal experiments separated two hypotheses: causal prior-target input helped substantially; future supervision by itself helped less. The field test is designed to determine whether that offline difference survives closed-loop driving.

## Limitations

- The July 13 field record is qualitative and operator-reported.
- Exact route, lighting measurements, weather, duration, takeover count, and clip IDs were not saved.
- Series 4 has no physical-car result yet.
- Steering success does not validate LiDAR, GPS, dashboard, or pedestrian behavior.
- The model is one component in a supervised system, not an independent safety mechanism.

See the [Series 3 table](../../ai-and-models/model-zoo/series-3.md), [Series 4 table](../../ai-and-models/model-zoo/series-4.md), and [evaluation PDF](../../steering_model_report.pdf).
