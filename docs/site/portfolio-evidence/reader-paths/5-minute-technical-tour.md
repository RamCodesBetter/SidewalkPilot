# 5 Minute Technical Tour

This path gives a technical or media reviewer enough context to describe SidewalkPilot accurately without reading the entire repository.

## 1. The System

SidewalkPilot uses three Linux computers with separate roles. The Raspberry Pi 5 owns hardware and safety. The Jetson runs the neural network over a private Ethernet link. The Zero 2 W renders telemetry over a dedicated USB network.

Read: [System At A Glance](../../start-here/system-at-a-glance.md) and [Data Flow](../../autonomy-stack/architecture/data-flow.md).

## 2. The Model Journey

Series 1 proved direct image-to-steering control at 200x66 resolution. Series 2 refined data and preprocessing. Series 3 increased the image to 320x180 and, from v3.1 onward, used a hybrid 19-value head: nine class logits, nine class-local offsets, and one throttle value.

The current field winner is v3.4. It did not win merely because of mean error. Its balanced turn metrics and physical behavior were stronger than v3.4b, while v3.3 and v3.3b demonstrated that more aggressive shadow augmentation could regress the car.

Read: [Series 3](../../ai-and-models/model-zoo/series-3.md), [B Checkpoints](../../engineering-process/design-decisions/b-checkpoints.md), and [Model Claim](../claims-and-proof/model-claim.md).

## 3. The Data Loop

Manual drives save images with absolute physical steering and throttle labels. The trainer uses time-grouped splits so neighboring frames do not appear on both sides of validation. Offline evaluation measures direction balance as well as numeric error. The final gate is a supervised physical run.

Read: [Model Iteration Method](../../engineering-process/iteration-records/model-iteration-method.md) and [Field Failure To Dataset](../../engineering-process/iteration-records/field-failure-to-dataset.md).

## 4. The Safety Boundary

The learned model controls autonomous steering. LiDAR does not pick a path; it watches the center corridor and can reduce throttle or hard-brake. Multi-lane swerve logic was removed because obstacle points alone cannot prove that the adjacent ground is safe sidewalk.

Read: [LiDAR Overview](../../autonomy-stack/lidar-safety/overview.md), [Distance Regions](../../autonomy-stack/lidar-safety/distance-regions.md), and [Why LiDAR Does Not Steer](../../autonomy-stack/lidar-safety/override-steering.md).

## 5. A Systems Failure That Mattered

Manual steering once became smooth for several seconds, paused, then resumed. The Bluetooth controller itself tested instantaneous. The actual problem was blocking application work, including waits on a powered-off Jetson. Network inference moved to a latest-frame worker, recurring filesystem and temperature subprocesses left the loop, and physical testing with the Jetson off confirmed the delay was removed.

Read: [Runtime Loop](../../runtime-code/runtime-loop.md).

## 6. What A Reviewer Can Verify

- Runtime and training source: [GitHub](https://github.com/RamCodesBetter/SidewalkPilot)
- Model and dataset artifacts: [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat)
- Training records: [Weights & Biases](https://wandb.ai/Sidewalk-Pilot/SidewalkPilot/table?nw=nwusersidewalkpilot)
- Demonstration channel: [YouTube](https://www.youtube.com/@SidewalkPilot)
- Claim-to-artifact index: [Evidence Map](evidence-map.md)

## Evidence Limits

The July 13 v3.4 comparison is a valid operator field verdict but not a fully instrumented benchmark: exact route, weather, takeovers, and clip IDs were not recorded. LiDAR's latest center-only policy also still needs a preserved physical test report. Those gaps are stated so future testing can close them.
