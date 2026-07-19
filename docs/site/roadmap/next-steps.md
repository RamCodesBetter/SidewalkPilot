# Next Steps

This page contains work that is not yet a proven capability.

| Priority | Planned work | Dependency | Success gate |
|---:|---|---|---|
| 1 | Integrate v4.1 and replay the v4.0 steering-echo cases | Live contract support and preserved failure clips | Every candidate uses the correct inputs and does not blindly repeat prior predictions |
| 2 | Preserve a physical test of current LiDAR slowdown/hold/emergency behavior | Controlled obstacle setup | Repeatable pass/fail record with AEB state and distances |
| 3 | Field-test the v4.1 models that pass replay | Fixed supervised route, v3.4/v4.0f controls | Logged shadow/turn runs with hashes, clips, takeovers, and a clear verdict |
| 4 | Publish reviewed v4.1 models only after their status is clear | Integration and field verdict | Clean Hugging Face repositories/cards with exact contracts and evidence limits |
| 5 | Collect the next targeted field dataset | A repeatable failure from the model comparison | New batch closes the named gap without changing unrelated data |
| 6 | Strengthen external technical collaboration | Reproducible logs and privacy review | A collaborator can inspect useful records without relying on autonomy claims |
| 7 | Evaluate larger-scale hardware integration | Stable current system and documented requirements | A reviewed design improves reliability without weakening serviceability or safety |

Quantization is not a current requirement because FP32 ONNX Runtime/CUDA meets the operating target. It should return to the roadmap only if measured latency, power, or memory creates a real constraint.

## Technical Workstreams

- **Retraining:** only after a repeatable failure identifies a coverage gap; preserve the old baseline and change one major factor at a time.
- **Sensor fusion:** evaluate IMU/GPS/speed feedback only against a defined failure and with stale-data behavior specified. More sensors do not automatically improve control.
- **Turn-in-shadow collection:** collect both directions, ordinary-turn controls, multiple shadow geometries, and route/run metadata rather than only filling steering buckets.
- **Jetson Orin Nano optimization:** measure latency, power, and memory before considering FP16, INT8, QAT, TensorRT, or a new deployment stack.
- **PCB:** redraw Rev B against the frozen runtime pinout, review power/connectors, then fabricate and bench-test before field installation.
- **Documentation media:** keep the checked-in draw.io sources and SVG exports synchronized with the code, and add a wiring/power diagram after the physical layout is finalized.

No item on this page should be described elsewhere as complete until its success gate is met.
