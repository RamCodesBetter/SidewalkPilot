# Research Scope and Limits

SidewalkPilot is a solo-built research and learning platform. It is not a product, a road-legal vehicle, or a certified autonomous system. This boundary applies to every model, demonstration, and result in the documentation.

## What the Project Is

SidewalkPilot is a physical RC-scale platform used to study the complete camera-steering engineering loop:

- Collecting and correcting real field data;
- Training and comparing custom neural networks;
- Deploying GPU inference to a Jetson Orin Nano: Series 1/2 through PyTorch CUDA and Series 3/4 through ONNX Runtime CUDA;
- Controlling real motors and steering from a Raspberry Pi 5;
- Keeping manual takeover and deterministic LiDAR braking independent of the model;
- Recording telemetry on a separate Zero 2 W dashboard;
- Turning field failures into the next data or code revision.

The value is the integration and iteration, not a claim that one neural-network score establishes general autonomy.

## What Has Been Demonstrated

- Physical camera-to-steering runs under operator supervision.
- v3.4 handled every shadow case presented in one July 13 comparison and was selected over v3.4b/v3.3/v3.3b for current use.
- A published 81,237-image real Series 3/4 dataset supports reproducible training work.
- Fifty-two checkpoints can be decoded and compared on one frozen challenge subset.
- LiDAR software can govern throttle and command emergency braking without choosing steering direction.
- Manual steering remained responsive in a hardware retest with Jetson Orin Nano powered off after network work moved outside the control loop.
- Six v4.0 models completed training, ONNX export, offline evaluation, runtime compatibility checks, and supervised field testing.
- Six v4.1 correction models completed training, ONNX export, and offline evaluation.

## Evidence Limits

- The July 13 v3.4 result is qualitative. Exact route, weather, takeover count, and clip identifiers were not preserved.
- The v4.0 field result is qualitative rather than a repeated route-controlled benchmark. v4.1 is runtime-supported but has not completed physical testing.
- Offline metrics do not prove obstacle avoidance, pedestrian response, recovery from a road-edge error, or operation outside the test distribution.
- The LiDAR policy has automated software tests, but the latest configuration still needs a preserved physical test record.
- GPS/navigation code exists, but it does not make the car safe for unattended route execution.
- The project has not received third-party safety validation or certification.

## Operating Boundary

- A human operator remains present with the controller and immediate stop authority.
- Tests are bounded, directly supervised, and do not authorize autonomous public-road operation.
- The car is not operated unattended.
- Autonomy is not armed when required sensors, manual controls, model inference, or braking checks fail.
- LiDAR does not steer around obstacles. It slows, holds, or emergency-brakes in the center corridor.
- New models remain experimental until a documented field comparison promotes them.

The platform is not authorized for public-road autonomy, unattended use, uncontrolled pedestrian operation, all-weather driving, or safety-critical service. A selected sidewalk test route does not become a closed course merely because it is familiar. Testing stops when people, traffic, weather, visibility, hardware, or system freshness violate the planned setup.

## Reporting Rules

1. Label a result as offline, bench, or field evidence.
2. Distinguish exact measurements from qualitative operator observations.
3. Do not convert “worked in the tested cases” into “works in all cases.”
4. Do not call a trainer-selected checkpoint the best driving model without field evidence.
5. Keep planned work separate from implemented work.
6. Preserve the model hash, route, conditions, clips, logs, and takeovers for future field claims.

See [Safety Overview](../safety-case/safety-overview.md), [Operating Limits](../safety-case/operating-limits/where-it-can-run.md), and [Evidence Map](../portfolio-evidence/reader-paths/evidence-map.md).
