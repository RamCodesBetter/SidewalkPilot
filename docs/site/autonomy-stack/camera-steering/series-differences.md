# Series Differences

Series 1/2, Series 3, and experimental Series 4 are different answers to the same question:
look at a sidewalk and decide how to steer. They differ in architecture, input history,
output horizon, deployment target, and evaluation criteria.

## How it works

| | Series 1/2 (`SteeringAutonomyV2`) | Series 3 (`SidewalkPilotV3`) | Series 4 experimental (`SidewalkPilotV4`) |
|---|---|---|---|
| Params | ~0.67M | ~5.5M | ~5.54-5.57M, contract-dependent |
| Image input | 200x66 | 320x180 | 320x180 |
| Temporal input | none | none | none for CF; three previous targets for PC/PCF |
| Head | single `tanh` regression | 9 logits + 9 offsets + throttle | 18 values per steering horizon, no throttle |
| Horizons | current steering | current steering/throttle | current only for PC; current + three future for CF/PCF |
| Runs on | Pi | Jetson "Jon" | Jetson runtime-supported; not field-promoted |
| Throttle | fixed runtime value | present in contract, disabled in steering-focused training | runtime-owned; removed from learned output |

The nine Series-3 buckets are HL, L, L+, SL, ST, SR, R, R+, HR. Series 1 uses an output
scale of `86.0°`, Series 2 uses `85.0°` (`SERIES_1/2_STEERING_OUTPUT_SCALE_DEG`), and the
runtime picks Series by the model-choice prefix (`steering_model_series()`: `2.` → Series 2,
else Series 1).

## Design progression

Series 1/2 established the compact Pi-capable regression path. v3.0 tested a larger
regression model on 320x180 input. v3.1 and later changed the steering contract to a class
plus within-class offset, which makes class recall directly measurable while retaining a
continuous angle. The Series 3 graph also contains a throttle output, but current training
and deployment do not use learned throttle. The larger visual model is deployed on Jon;
the project has not published a Pi-versus-Jon latency benchmark for this architecture.

## Key findings

- **Turn-vs-shadow observation.** Some field-tested iterations that reacted more strongly
  to turn cues also followed shadow edges; more center-biased checkpoints could miss turns.
  Targeted turn-in-shadow data is the current collection response, not a claim that one data
  type is mathematically guaranteed to solve every case.
- **MAE is insufficient.** A center-biased checkpoint can score well on a straight-heavy
  set while retaining weak turn recall. Series 3/4 comparisons therefore include Bal9,
  turn exact, turn +/-1, ST exact, signed error, and physical testing.

v3.4 is the current field-selected baseline. In the July 13 comparison it handled every
presented shadow case; v3.4b was slightly worse, v3.3 was worse than v3.2, and v3.3b was
much worse than v3.2b. All three Series 4 runs completed. Their six ONNX artifacts passed
signature and CUDA inference checks, and the Jetson runtime supports all three contracts.
No Series 4 field test has occurred, so offline results order candidates but do not select
a field baseline.

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
