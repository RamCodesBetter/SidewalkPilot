# Retest Policy

When a model version or config change counts as "verified": what has to be re-run before I trust it, and why offline eval alone is never enough.

## How it works

The policy is a two-gate rule. A change is not "done" until it passes both an offline gate and a field gate, in that order.

**Offline gate.** Run `code/test_files/evaluate_sidewalkpilot_models.py` and read Bal9, turn exact, turn +/-1, straight exact, error magnitude, signed bias, and the confusion matrix. The offline gate catches gross regressions cheaply before hardware time. Passing it means "worth field-testing," not "good."

**Field gate.** Drive the car on the real situation the change was meant to fix. A compatible ONNX must exist on Jon and the version must exist in `STEERING_MODEL_VERSIONS`. Series 4 also requires the correct runtime contract: image-only CF or causal history for PC/PCF. Then re-drive the specific failing scenario, such as the shadow band that caused shadow-chasing or the mid-right turn that was missed, and confirm the behavior actually changed on the car.

A critical operational catch sits underneath this: a config or code change only takes effect after the owning *process* re-imports it, on every device. Reloading via the `car` / `dash` / `ai` aliases restarts the process; editing a file on disk while the old process is still running verifies nothing. So "retest" always means "restart the owning process first, then observe."

## Why this choice

Offline metrics can miss the behavior that matters physically. A low MAE or validation loss can coexist with weak turn recall, and the recorded v3.1b field test exposed behavior not represented by its headline offline value. That bounded result is why the field gate remains mandatory.

## Decision record

| Section | Content |
|---|---|
| Decision | Two-gate retest: offline bucket/confusion check first, then a mandatory field re-drive of the exact failing scenario, with the owning process restarted before observing. |
| Alternatives | (a) Offline-eval-only sign-off — rejected: MAE/loss reward straight-collapse and miss real failures (v3.1b). (b) Field-only — rejected: wastes hardware time on models a cheap eval would have killed. (c) Verify from disk without restart — rejected: stale process silently runs old code. |
| Reason | Offline metrics are necessary but not sufficient; the failures that matter (shadow-chasing, argmax flips, lighting) only appear on the car, and only after the process re-imports the change. |
| Test gate | Passes bucket/confusion eval AND drives the original failing situation correctly, observed on a freshly restarted process. |

## Evidence to attach

- Eval JSON (bucket distribution) for the retested version.
- Field re-drive note / clip of the specific scenario.
- Confirmation of which process was restarted on which device (Pi `car`, Zero `dash`, Jon inference service).

## Related pages

- `engineering-process/design-decisions/b-checkpoints.md`
- `testing/failures/overview.md`
- `roadmap/next-steps.md`
