# 30 Second Overview

**SidewalkPilot is a real autonomous RC car and an end-to-end engineering project that began in April 2025.** A Jetson Orin Nano runs the camera-steering model, a Raspberry Pi 5 owns hardware and independent LiDAR braking, and a Zero 2 W renders live telemetry.

The project includes 52 evaluated steering checkpoints across four model series and a published 81,237-image real sidewalk dataset. The field-selected model, **v3.4**, was chosen after it completed every harsh-shadow case presented in a July 2026 comparison. Series 4 tests previous steering context and future-target supervision: all six v4.0 models were field-tested, and six corrective v4.1 models are trained and awaiting runtime integration.

The engineering loop covers mechanical calibration, power and wiring, Python control, data capture, GPU training, ONNX/CUDA deployment, class-balanced evaluation, real failures, LiDAR safety, and public artifacts.

It is not a road-legal or unattended autonomous vehicle. Tests are supervised and bounded, with the controller held for intervention. Worst-case override latency has not been characterized.

Fast proof:

- [5 Minute Technical Tour](5-minute-technical-tour.md)
- [System architecture](../../start-here/system-at-a-glance.md)
- [Series 3 results](../../ai-and-models/model-zoo/series-3.md)
- [Series 4 results](../../ai-and-models/model-zoo/series-4.md)
- [Engineering timeline](../../start-here/build-timeline.md)
- [Evidence and limits](evidence-map.md)
- [GitHub](https://github.com/RamCodesBetter/SidewalkPilot)
- [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat)
