# Field Failure to Dataset

Field failures are converted into training evidence only when the failure, labels, and intended correction stay connected.

## Capture Procedure

1. Record model version, date/time, route segment, lighting, weather, and AEB state.
2. Preserve the camera images, CSV log, and any video covering the event.
3. Identify whether the problem came from model perception, mechanical steering, controller/runtime delay, sensor health, or operator input.
4. Keep logical `0..180` steering labels and absolute physical throttle fractions in the dataset. Servo trim and reference throttle ranges belong in runtime policy, not historical label rewriting.
5. Add correction labels only through the project correction metadata so filenames and targets remain auditable.
6. Tag the purpose of the new data: shadow, turn, evening, surface, road-entry, or another specific failure class.
7. Recount images and labels and reject missing, duplicate, or corrupt files before training.

## Example: Harsh Tree Shadows

**Observed behavior:** a camera model interpreted a diagonal dark boundary as the sidewalk edge and steered along it.

**Data response:** collect real frames across bright and dark sidewalk regions, preserve genuine steering labels, and add synthetic shadow/lighting augmentation during training.

**Iteration result:** stronger augmentation in v3.3 did not solve the problem and damaged field behavior. The rebalanced v3.4 training produced the selected result.

**Evidence lesson:** collecting the right failure is necessary, but augmentation strength and class balance still determine what the model learns.

## Example: Left Drift Was Not Automatically a Label Problem

A large batch of images initially appeared left-biased. Mechanical inspection and servo testing showed that vehicle trim, linkage load, and directional hysteresis could create the same visual pattern. Deleting or relabeling every frame would have hidden a hardware issue inside the dataset.

The project therefore separates:

- Physical steering calibration;
- Absolute labels saved at capture time;
- Reference steering shown to models and operators;
- Model prediction bias measured offline.

## Dataset Acceptance Checks

A collection is ready only when:

- Every label references an existing image;
- Every training image has one valid label record;
- Corrupt images are removed from both disk and metadata;
- Steering values remain in the documented absolute range;
- Source and purpose are recorded;
- Time order remains available for grouped splitting;
- Counts are written into the dataset card or release record.

## Required Field Record Template

```text
Date/time:
Route/segment:
Model and artifact hash:
Lighting/weather:
AEB and calibration state:
Autonomous duration/distance:
Manual takeovers and reasons:
Observed failure:
Image/CSV/video filenames:
Dataset tag and accepted count:
Hypothesis for next run:
Promotion or rollback decision:
```

The July 13, 2026 model comparison predates this complete standard. It has a useful qualitative verdict, but missing route, weather, takeovers, and clip identifiers are preserved as evidence gaps rather than reconstructed after the fact.
