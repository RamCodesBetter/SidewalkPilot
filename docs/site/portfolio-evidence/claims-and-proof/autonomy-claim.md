# Autonomy Claim

## Defensible Claim

SidewalkPilot has demonstrated supervised camera-based steering on a physical RC car, with Raspberry Pi control arbitration, Jetson inference, manual takeover, logging, and an independent LiDAR slowdown/braking layer.

The project does **not** claim SAE driving automation, unattended operation, public-road readiness, or safe operation around arbitrary pedestrians.

## What Autonomous Means Here

When autonomy is enabled:

1. the Raspberry Pi captures and submits the newest camera frame;
2. the Jetson predicts steering from the selected ONNX model;
3. the Raspberry Pi accepts only a fresh result;
4. the model supplies autonomous steering;
5. runtime policy and enabled LiDAR AEB can reduce or stop longitudinal motion;
6. the human operator can brake, take over, or quit.

LiDAR does not autonomously choose an avoidance path. That division is intentional: the camera model sees the sidewalk, while the current LiDAR policy only has enough information to constrain forward motion.

## Supporting Evidence

- Physical-run demonstrations on the [YouTube channel](https://www.youtube.com/@SidewalkPilot).
- Production runtime in `code/controller/current/`.
- Fresh-result and powered-off-Jetson behavior in `rc_car_app/runtime.py` and its async-client tests.
- Public ONNX models and cards on [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat).
- Model-level evidence in the [Model Claim](model-claim.md).
- Safety boundaries in [LiDAR AEB](../../autonomy-stack/lidar-safety/aeb.md).

## Failure Boundaries

The system must not be described as autonomous outside its tested envelope. Known boundaries include:

- harsh lighting and shadows remain a continuing generalization risk even after v3.4;
- an empty or stale LiDAR scan can fail to produce an intervention;
- a disconnected Jetson removes autonomous steering but must not block manual control;
- USB dashboard failure removes telemetry, not control authority;
- GPS/navigation software does not by itself make a route safe;
- the operator remains responsible for the environment and shutdown.

## Promotion Standard

A model is not promoted from offline metrics alone. It must load through the production ONNX path, return the expected output contract, preserve manual responsiveness, and pass supervised route testing. A fully auditable future run should also save route, weather, duration, takeover count, logs, and video identifiers.
