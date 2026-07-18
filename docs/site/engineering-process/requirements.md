# Requirements and Success Criteria

SidewalkPilot is a supervised physical autonomy project. Requirements are ordered around
evidence: clean data, camera steering, independent motion constraints, route planning,
manual control, and enough observability to explain every result.

## Project Goals

1. **Maintain traceable training data.** Preserve logical steering, absolute physical
   throttle, source provenance, ordered capture context, exclusions, and failure-driven
   coverage.
2. **Steer from the camera.** Run the selected model through its matching preprocessing,
   output decoder, and Jetson Orin Nano deployment contract.
3. **Keep control bounded.** Preserve manual takeover, reject stale autonomous results,
   and let enabled center-corridor LiDAR policy cap or stop forward motion without steering.
4. **Plan mapped routes.** Use GPS and A* to create sidewalk and manual-crossing segments.
5. **Make state observable.** Preserve dashboard telemetry, CSV logs, training records,
   model artifacts, and field evidence.

The goal is a repeatable field-to-data-to-model-to-car engineering loop, not one successful
drive or one low evaluation number.

## Current Non-Goals

The project does not claim public-road autonomy, unattended operation, pedestrian
classification, universal obstacle detection, LiDAR steering, guaranteed avoidance,
safety certification, all-weather reliability, a measured hard autonomous speed limit,
deployed FP16/INT8/TensorRT inference, Series 4 field superiority, a fabricated custom PCB,
or bit-identical training across unrelated GPU/software environments.

## Design Constraints

| Area | Constraint |
|---|---|
| Camera | Camera Module 3 Wide capture and physical orientation must match the dataset path |
| Steering | Logical labels remain 0-180; PCA9685 mapping and trim remain hardware concerns |
| LiDAR | FHL-LD19 uses a CP2102 UART-to-USB Adapter at 230400 baud; missing scans are not proof of clearance |
| GPS/IMU | GPS uses `/dev/ttyAMA0`; experimental yaw feedback uses the XIAO MG24 path |
| Compute | Jetson Orin Nano is the AI Model Manager for asynchronous Series 3/4 ONNX inference; Raspberry Pi 5 applies hardware and safety control |
| Dashboard | Zero 2 W telemetry uses the dedicated USB network with no current Wi-Fi fallback |
| Data | Series 3/4 use the published 81,237-image real dataset; historical source-mix claims require run evidence |
| Promotion | Offline metrics select candidates; only physical testing changes the field baseline |

## Success Criteria

| Area | Required evidence | Current state |
|---|---|---|
| Manual responsiveness | Direct controller test plus running-car test without periodic pauses | Observed after blocking work left the control path; long-duration latency trace remains open |
| Camera and inference | Captured frames, matching preprocessing, fresh result, correct model/version | Implemented; v3.4 is the field-selected baseline |
| Shared evaluation | Frozen subset, evaluator revision, JSON, and PDF | Complete for 46 checkpoints on 6,952 frames |
| Model promotion | Balanced metrics plus repeatable testing of ordinary turns and target failure cases | v3.4 selected; Series 4 pending |
| LiDAR policy | Deterministic 1.65/1.25/1.05 m tests and confirmation that steering remains untouched | Implemented in software |
| Physical braking | Repeated tests under recorded payload, surface, battery, and speed | Preserved result pending |
| Navigation | Followable A* route with correct automatic/manual segment boundaries | Implemented in code; end-to-end GPS field record pending |
| Dashboard and logs | Live non-stale USB display and complete run CSV | Implemented; link recovery tooling exists |

No single metric proves steering quality. Bal9, turn exact, turn within one class, straight
recall, mean/median error, signed bias, confusion behavior, and physical driving are read
together.

## Verification Gates

### Code

Compile every changed Python entrypoint or module before hardware testing. Validate shell
installers with `bash -n`. A configuration edit is not active until the owning process has
restarted and imported it.

### Subsystems

| Change | Minimum gate |
|---|---|
| Controller mapping | Confirm printed mapping and physical button/stick behavior |
| Steering | Restrained 0/90/180 direction check; compensation remains in hardware mapping |
| Model runtime | Verify artifact, ONNX signature, preprocessing, decoder, freshness, and provider |
| LiDAR/AEB | Verify center-corridor thresholds, no steering output, stale behavior, and reconnect |
| Navigation | Verify route, edge types, automatic/manual segments, handoff, and resume |
| Dashboard | Trace changed telemetry from calculation through serialization, transport, receipt, and rendering |
| Logging | Match CSV headers to row values and confirm a real file is written |

### Hardware

- Start steering and motor tests with the car restrained or wheels unloaded and the controller ready.
- Verify USB dashboard addresses, carrier, neighbors, and ping in both directions.
- Stop competing services before opening raw LiDAR serial.
- Confirm the selected model and enabled safety state before autonomous motion.

### Data and Models

Before accepting a dataset batch, count images and labels, flag corrupt files, inspect
lighting/blur/obstruction and steering coverage, preserve provenance, and document
exclusions. Do not delete data without review.

Before promoting a model, run the common evaluator, inspect class balance and confusion,
export and load the exact ONNX artifact, restart affected services, then drive the same
ordinary-turn and motivating-failure cases. Final and best-validation checkpoints are
separate candidates; neither role wins automatically.

## Claim Rule

Code proves implementation, not physical performance. A valid field claim records the
model hash, code revision, route, conditions, calibration and AEB state, autonomous
distance or duration, takeovers and reasons, logs, video, and the keep/rollback decision.

See [Model Iteration Method](iteration-records/model-iteration-method.md), [Current Status](../start-here/current-status.md), and [Safety Overview](../safety-case/safety-overview.md).
