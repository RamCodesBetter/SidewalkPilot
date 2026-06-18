# Next Steps

TODO:

- [ ] Implement measured steering calibration from the Desmos steering-fit graph:
  [Fix Servo Trim Graph](https://www.desmos.com/calculator/sdwx6h3vpx).
- [ ] Treat real servo `26.45558 deg` as the software left limit for logical steering `0 deg`, while keeping real servo `90 deg` as logical center and real servo `180 deg` as logical right.
- [ ] Add a piecewise logical-to-real steering conversion so sidewalk driving and training labels use the symmetric logical range, but hardware still receives the measured real servo command.
- [ ] Log both `steering_logical_deg` and `steering_servo_real_deg` in future photo labels and CSV telemetry so model training stays hardware-calibrated but debugging remains tied to the actual PCA9685 command.
- [ ] Validate the calibration on a short route before counting new images toward the 5,000-image v3.0 dataset; pass condition is that release-to-center behavior and left/right curve shape are visibly more symmetric.
- [ ] Add page-specific notes for `roadmap/next-steps.md` after inspecting the real project files.
- [ ] Cross-link `Next Steps` to the most relevant code, data, testing, and safety pages.
- [ ] State what is already proven before listing future work.
- [ ] Separate near-term fixes from long-term research ideas.
- [ ] List dependencies, risks, and test gates for this next step.
- [ ] Add what data, hardware, or code must change.
- [ ] Add how success would be measured.
- [ ] Keep future claims clearly marked as planned, not completed.
- [ ] Add the exact source path, artifact path, or hardware component name.
- [ ] Add the command or procedure needed to reproduce the result.
- [ ] Add expected inputs and outputs.
- [ ] Add the settings, flags, constants, or calibration values that control it.
- [ ] Add known failure modes and how they appear in logs, video, or field behavior.
- [ ] Add validation steps and pass/fail criteria.
- [ ] Add links to related pages that a public reader should follow next.
