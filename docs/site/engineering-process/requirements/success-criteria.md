# Success Criteria

The project separates code implementation, observed field behavior, and pending validation. A source-code path is not automatically a physical safety result.

## Platform

| Criterion | Required evidence | Current status |
|---|---|---|
| Responsive manual control | `jstest` plus a running-car input test with no periodic stalls | Observed after moving camera/Jon work off the control-loop path |
| Camera capture | Picamera2 startup plus saved/processed frames | Implemented and used for data collection |
| Dashboard link | Bidirectional USB ping and live, non-stale display updates | Implemented; recovery tooling exists for known link failures |
| LiDAR reconnect | Disconnect/reconnect log and resumed points | Implemented in the reader; retain a repeatable hardware record |
| Per-run logs | CSV file with the current 46-column schema | Implemented |

## Model

| Criterion | Required evidence | Current status |
|---|---|---|
| Shared offline comparison | Frozen subset, exact evaluator revision, JSON and PDF | Complete for 46 checkpoints on 6,952 frames |
| Shadow/turn behavior | Same supervised field cases for each candidate | v3.4 selected on July 13; Series 4 pending |
| Field promotion | Better field behavior without unacceptable lag or instability | v3.4 remains default |

Bal9, turn exact, turn +/-1, straight exact, MAE, median error, and signed error are read together. No single offline column establishes driving quality.

## Safety

| Criterion | Required evidence | Current status |
|---|---|---|
| LiDAR never steers | Unit tests and runtime inspection | Implemented |
| Governor thresholds | Deterministic policy tests at 1.65, 1.25, and 1.05 m | Implemented in code |
| Physical stopping performance | Repeated obstacle tests under actual payload, surface, battery, and speed | Pending preserved results |
| Manual takeover | Operator cancels autonomy immediately in a controlled test | Required for every field session |
| Hard speed limit | Measured-speed governor in final throttle path | Not implemented; `MAX_AUTONOMOUS_SPEED_MPH` is declaration only |

## Publication Rule

Only claim what the evidence supports. Series 4 can be described as trained, exported, evaluated, CUDA-smoke-tested, and runtime-supported. It cannot yet be described as field-proven or better than v3.4 on the car.
