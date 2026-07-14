# 30 Second Overview

**SidewalkPilot is a real autonomous RC car built as an end-to-end engineering project.** A camera model running on an NVIDIA Jetson steers the vehicle, a Raspberry Pi operates the hardware and independent LiDAR braking, and a Zero 2 W displays live telemetry.

The project has progressed through more than forty regular and best-validation checkpoints across three model series. The current field-selected model, **v3.4**, was chosen after it completed every harsh-shadow case presented in a July 2026 comparison. That result addressed a repeated failure where earlier models mistook diagonal tree shadows for sidewalk edges.

The work includes the full loop: mechanical calibration, electronics, Python runtime, data collection, GPU training, ONNX deployment, offline evaluation, field failures, safety design, and public model/dataset publishing.

What it is not: a road-legal or unattended autonomous vehicle. Tests are supervised and bounded, with manual takeover available.

Fast proof:

- [Project architecture](../../start-here/system-at-a-glance.md)
- [Series 3 results](../../ai-and-models/model-zoo/series-3.md)
- [Engineering timeline](../../start-here/build-timeline.md)
- [Safety limits](../../safety-and-ethics/limits.md)
- [GitHub](https://github.com/RamCodesBetter/SidewalkPilot)
- [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat)
- [YouTube](https://www.youtube.com/@SidewalkPilot)
