# SidewalkPilot

SidewalkPilot is a solo-built autonomous RC-car research platform for sidewalks. A camera model proposes steering, a separate LiDAR safety layer can slow or stop the car, GPS software provides route context, and a live LED dashboard exposes system state. The project runs on an Jetson Orin Nano, Raspberry Pi 5, and Zero 2 W.

<table width="100%">
<tr>
<td valign="top" align="left">

- [Documentation](https://ramcodesbetter.github.io/SidewalkPilot/)
- [YouTube](https://www.youtube.com/@SidewalkPilot)
- [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat)
- [Parts list](https://1drv.ms/x/c/9685d41907cf4e28/IQAZPTqPm5FDRLypIrzf-Jv5AapVDVfyFpqjfn2W666oeXk?e=3MadEB)
- [Email](mailto:ramsabavat2012@gmail.com)

</td>
<td valign="top" align="right">
<img src="docs/media/sidewalkpilot-demo.gif" alt="SidewalkPilot autonomous sidewalk-driving demonstration" width="300">
</td>
</tr>
</table>

> SidewalkPilot is a supervised research and learning project used on controlled test routes with the operator present. It is not presented as certified or approved for unattended or public-road operation.

## Current Result

**SidewalkPilot v3.4** is the current field-selected steering model. During the July 13, 2026 comparison, v3.4 handled every shadow case presented and the tested normal left/right turns. v3.4b was slightly worse, v3.3 was worse than v3.2, and v3.3b was much worse than v3.2b. The observation is valuable but qualitative because route, clip, weather, and takeover metadata were not preserved.

Series 4 is a parallel temporal-learning experiment on the same 81,237-image Series 3/4 dataset. Six artifacts have been trained and offline-evaluated:

| Experiment | Final epoch | Best steering-MAE epoch | Runtime contract |
|---|---|---|---|
| Previous + current (PC) | v4.0p | v4.0r | image + three prior steering targets -> current steering |
| Current + future (CF) | v4.0f | v4.0g | image -> current plus three future steering horizons |
| Previous + current + future (PCF) | v4.0a | v4.0c | image + three prior targets -> current plus three future horizons |

All six Series 4 ONNX models are supported by the live Jetson Orin Nano runtime. None has been field-promoted yet, so v3.4 remains the deployed research reference.

## System Architecture

The computers have separate responsibilities:

| Manager | Hardware | Responsibility |
|---|---|---|
| AI Model Manager | Jetson Orin Nano | Receives the newest camera frame over dedicated Ethernet and runs ONNX Runtime/CUDA inference |
| Major System Manager | Raspberry Pi 5 | Controller input, camera capture, LiDAR, GPS, steering, motors, logging, and final safety arbitration |
| Display System Manager | Zero 2 W | Renders the Waveshare 64x32 HUB75 dashboard from UDP telemetry over a dedicated USB network |

The Raspberry Pi 5 remains authoritative. The Jetson Orin Nano proposes steering but never directly controls the servo. The Zero 2 W only displays telemetry. Manual controller input can cancel autonomy, and the enabled LiDAR policy can constrain or stop forward motion.

```text
Xbox controller ----------------------------+
Raspberry Pi Camera -> Raspberry Pi 5 -> Jetson Orin Nano steering model -+--> arbitration -> steering + motors
LiDAR --------------------------------------+         |
GPS, IMU, hall sensor ----------------------+         +--> logs + dashboard
```

Camera inference uses a background latest-frame client. Connection and inference waits occur in that worker rather than in the controller loop. One powered-off Jetson Orin Nano hardware retest no longer showed the earlier periodic steering pauses, but that observation is not a formal worst-case latency bound. The current LiDAR policy does not steer: it can progressively slow, hold, or emergency-brake inside a center corridor.

## Model Journey

SidewalkPilot has 46 trained steering checkpoints across four series:

- **Series 1:** compact 200x66 direct steering regression established the end-to-end image-to-servo loop.
- **Series 2:** retained the approximately 0.67M-parameter regressor while testing data cleanup, steering range, and HSV/CLAHE preprocessing.
- **Series 3:** moved to 320x180 images and an approximately 5.53M-parameter network. v3.1+ uses nine steering-class logits, nine class-local offsets, and one throttle output.
- **Series 4:** keeps the Series 3 visual backbone, removes throttle learning, and compares causal steering history and multi-horizon supervision. PC, CF, and PCF contain approximately 5.54M to 5.57M parameters.

The generated [steering-model report](docs/steering_model_report.pdf) evaluates all 46 models on the same frozen 6,952-frame challenge subset. Selection does not rely on MAE alone. The report includes balanced nine-class recall (Bal9), exact and adjacent turn recall, straight recall, median error, signed bias, and confusion matrices.

## Data and Training

Field runs record camera images paired with logical steering degrees (`0..180`) and absolute physical throttle fractions. Series 3 and 4 share a published 81,237-image real-world dataset. The trainer sorts images by path and groups them into 100-frame windows. Each window goes entirely into training or validation, which keeps most neighboring frames together. One capture run can still appear in both sets.

Training runs on an NVIDIA RTX 6000 Ada GPU. The Series 3/4 trainers support lighting, color, flip, and synthetic-shadow augmentation, save final-epoch and best-steering-MAE artifacts, export ONNX, and log to Weights & Biases. Physical field testing remains the promotion gate after offline evaluation.

## Hardware

| Function | Component |
|---|---|
| AI inference computer | Jetson Orin Nano |
| Hardware controller | Raspberry Pi 5 |
| Dashboard computer | Zero 2 W |
| Chassis | Yahboom Ackermann 520M |
| Vision | Raspberry Pi Camera Module 3 Wide |
| Obstacle distance | Youyeetoo FHL-LD19 360-degree LiDAR through CP2102 USB |
| Steering | PCA9685 PWM driver and high-torque steering servo |
| Drive | Yahboom AT8236 motor controller and DC motors |
| Navigation | BN880 GPS; onboard HMC5883L-compatible compass is currently bench-only |
| Motion feedback | Hall-effect wheel-speed sensor and external IMU |
| Manual control | Xbox Wireless Controller |
| Dashboard | Waveshare 64x32 HUB75 RGB LED matrix |

## Repository Map

| Path | Contents |
|---|---|
| `code/controller/current/` | Jetson Orin Nano inference server, Raspberry Pi 5 controller, and Zero 2 W dashboard runtime |
| `code/ai_models_datasets/series_1_and_2/` | Series 1/2 trainer and local dataset metadata |
| `code/ai_models_datasets/series_3_and_4/` | Series 3 trainer plus the three Series 4 trainers |
| `code/ai_models/` | Local/Hugging Face PTH and ONNX artifacts; binaries are ignored by Git |
| `code/test_files/` | Model evaluation, hardware tests, and calibration tools |
| `docs/site/` | MkDocs documentation source |
| `docs/steering_model_report.pdf` | Generated 46-model evaluation report |

## License

Apache 2.0. See [LICENSE](LICENSE).
