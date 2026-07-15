# Safety Claim

SidewalkPilot implements layered control safeguards. This is an implementation claim, not certification or proof of safe unsupervised operation.

## Implemented Layers

- Manual Xbox input can cancel autonomous control.
- The Pi rejects stale/unavailable autonomous model results.
- With AEB enabled, center-corridor LiDAR clearance can cap forward throttle in manual or autonomous drive.
- At or inside 1.05 m, the LiDAR policy requests zero throttle and a full hard brake.
- LiDAR never supplies steering; the camera model is the sole autonomous steering owner.
- Reverse excludes the forward AEB stop rule.
- A servo-write fault forces braking.

The throttle governor starts below 1.65 m, reaches 60% reference at 1.25 m, and holds that target until the 1.05 m emergency boundary. Sixty percent reference corresponds to 82% physical PWM under the current measured 55% motor dead-zone mapping. Saved labels remain absolute physical throttle.

## Evidence and Limits

Policy tests verify the configured logic, and 10 Hz CSV logging records the state used for later review. The current configuration still needs a preserved physical stopping-distance and false-trigger test under the actual payload. It cannot be claimed to detect every obstacle, classify pedestrians, keep the car inside every sidewalk, or support unattended use.
