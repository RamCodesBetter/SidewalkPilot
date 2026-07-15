# Related Work

SidewalkPilot uses an established behavior-cloning idea: pair forward-camera images with
human steering commands, then train a neural network to predict steering from a new image.
This page limits the comparison to claims supported by a primary source and does not imply
performance equivalence with road vehicles or commercial sidewalk robots.

## PilotNet lineage

NVIDIA's 2016 *End to End Learning for Self-Driving Cars* describes a convolutional network
trained from road images paired with human steering commands. The paper reports training on
an NVIDIA DevBox and inference on NVIDIA DRIVE PX. It is the direct historical reference for
SidewalkPilot's image-to-steering framing:

- [Bojarski et al., *End to End Learning for Self-Driving Cars* (NVIDIA PDF)](https://images.nvidia.com/content/tegra/automotive/images/2016/solutions/pdf/end-to-end-dl-using-px.pdf)
- [arXiv record](https://arxiv.org/abs/1604.07316)

SidewalkPilot borrows the supervised camera-to-steering concept. It does not reproduce the
paper's vehicle, dataset, compute platform, route, or validation protocol, so its metrics are
not compared numerically with PilotNet.

## Project-specific differences

- The target environment is a controlled sidewalk test route rather than a roadway.
- The deployed compute is split between a Raspberry Pi 5 and Jetson Orin Nano.
- Series 1/2 use direct steering regression. Most Series 3 checkpoints use nine steering
  classes plus a per-class offset; Series 4 adds temporal supervision or causal history.
- A separate center-corridor LiDAR policy can cap throttle or request a hard stop when AEB is
  enabled. It does not steer or classify objects.
- Evaluation includes Bal9, turn recall, signed error, confusion matrices, and supervised
  field tests because aggregate MAE alone can hide straight-biased behavior.

## Commercial sidewalk robots

Commercial sidewalk delivery robots are relevant product context, but this repository does
not contain a controlled comparison of their sensors, compute, cost, safety cases, speed, or
autonomy quality. SidewalkPilot therefore makes no claim that it matches or outperforms
Coco, Serve, Starship, or another commercial platform. The defensible comparison is only
the problem setting: small robots operating around sidewalk geometry.

## Scope of the comparison

This is an architectural lineage note, not a benchmark. SidewalkPilot's supported claims
come from its own code, saved datasets, offline report, and bounded field observations.

## Related pages

- `research-and-math/machine-learning/sim-to-real-gap.md`
- `ai-and-models/architecture/series-3-hybrid-head.md`
- `research-context/novelty-and-contributions.md`
