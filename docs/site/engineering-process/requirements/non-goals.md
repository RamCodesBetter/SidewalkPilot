# Non-Goals

The current project does not claim:

- Public-road autonomy or legal road-vehicle status;
- Unattended operation;
- Pedestrian classification or universal obstacle detection;
- LiDAR-based steering or guaranteed obstacle avoidance;
- An enforced 3.2 mph autonomous speed cap;
- TensorRT, FP16, or INT8 as the live inference path;
- Series 4 field performance before the planned comparison;
- A fabricated custom Raspberry Pi 5 breakout PCB; or
- Bit-identical training reproduction across different GPU/software stacks.

Series 3/4 training uses the published 81,237-frame real dataset. CARLA data is maintained separately. Whether a specific historical checkpoint included CARLA should be stated only from that run's recorded roots/logs, not inferred from series name or trainer capability.

These boundaries keep the documentation aligned with evidence and leave room for later experiments without presenting them as completed work.
