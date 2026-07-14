# Regular and `b` Checkpoints

Every SidewalkPilot training run can produce two public artifacts with the same architecture and data:

- **regular (`vX.Y`)**: weights at the final requested epoch;
- **best-validation (`vX.Yb`)**: weights from the epoch with the best configured validation objective.

The `b` suffix means checkpoint provenance, not guaranteed superiority.

## Why Keep Both

The final checkpoint shows where the full schedule converged. The best-validation checkpoint preserves an earlier point that may generalize better if later epochs overfit. Publishing both makes checkpoint selection auditable and exposes cases where the validation objective disagrees with field control.

## Field Evidence

The July 13, 2026 comparison is a direct example: v3.4 regular beat v3.4b on tested shadows and normal turns even though v3.4b had lower aggregate MAE and median absolute error. Validation favored more straight-biased behavior; the physical route favored stronger turn behavior and balance.

## Naming Rule

| Item | Regular | Best-validation |
|---|---|---|
| Model version | `3.4` | `3.4b` |
| ONNX file | `SidewalkPilot-v3.4.onnx` | `SidewalkPilot-v3.4b.onnx` |
| Hugging Face repo | `SidewalkPilot-v3.4` | `SidewalkPilot-v3.4b` |
| Card checkpoint role | `final-epoch` | `best-validation` |

Cards include chronological metrics only through their own version. A regular card includes earlier versions and itself; its `b` card may additionally include that paired regular model and itself.

## Promotion Rule

Neither suffix is promoted automatically. Compare output shape, artifact integrity, class-balanced and turn metrics, signed bias, command freshness, and the same field route. Production changes only after a recorded car verdict.
