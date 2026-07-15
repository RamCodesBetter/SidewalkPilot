# Harsh Sidewalk Surfaces

Expansion joints, cracks, repairs, leaves, stains, and mixed paving can change the
visual features available to camera steering. Their effect on a neural checkpoint
must be measured rather than inferred from one image.

## Two different paths

The repository contains a classic image-processing fallback that uses color and
edge heuristics. Its masks and edge fits can be disrupted by dark seams or strong
interior lines. That explains the fallback's mechanism, but it does not explain a
neural model failure.

Series 3/4 uses the learned ONNX model on Jon. Its response depends on training
coverage and learned features, and it does not expose a calibrated confidence for
surface familiarity. A fresh neural result is normally reported with confidence
`1.0`; the runtime will not necessarily stop merely because the pavement is
unusual.

## Evidence status

The historical dataset includes batches described as harsh-sidewalk captures, but
this page does not have a linked, repeated field benchmark for surface changes.
No claim is made that v3.4 or a Series 4 candidate handles every crack, patch, or
paver surface.

## Test method

Use a supervised route with identified surface transitions. Preserve video, CSV,
model hash, route position, steering behavior, and takeover count. Repeat the same
transitions with the v3.4 control and each candidate before attributing a change
to the model.

## Related pages

- [Field Testing](../field-testing/overview.md)
- [Operating Limits](../../safety-and-ethics/limits.md)
- [Model Retest Plan](../field-testing/model-retest-plan.md)
