# Next Steps

This page contains work that is not yet a proven capability.

| Priority | Planned work | Dependency | Success gate |
|---:|---|---|---|
| 1 | Compare all six Series 4 models with v3.4 | Jon deployment and fixed supervised route | Logged shadow/turn runs with hashes, clips, takeovers, and a clear verdict |
| 2 | Preserve a physical test of current LiDAR slowdown/hold/emergency behavior | Controlled obstacle setup | Repeatable pass/fail record with AEB state and distances |
| 3 | Publish only the Series 4 artifacts that pass review | Prior field verdict | Clean Hugging Face repos/cards with exact contracts and evidence limits |
| 4 | Collect the next targeted field dataset | A repeatable failure from the model comparison | New batch closes the named gap without changing unrelated data |
| 5 | Strengthen external technical collaboration | Reproducible logs and privacy review | A collaborator can inspect useful records without relying on autonomy claims |
| 6 | Evaluate larger-scale hardware integration | Stable current system and documented requirements | A reviewed design improves reliability without weakening serviceability or safety |

Quantization is not a current requirement because FP32 ONNX Runtime/CUDA meets the operating target. It should return to the roadmap only if measured latency, power, or memory creates a real constraint.

No item on this page should be described elsewhere as complete until its success gate is met.
