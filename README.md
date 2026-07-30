# SidewalkPilot

SidewalkPilot is my RC car that can self-drive on sidewalks. The Jetson Orin Nano is the
AI brain for every live-selectable steering-model family: Series 1/2 use PyTorch CUDA and
Series 3/4 use ONNX Runtime CUDA. It returns the steering prediction. A Raspberry Pi 5 captures the camera and sensors, applies
safety rules, and controls the hardware, while a Zero 2 W renders the live LED dashboard.

<table width="100%">
<tr>
<td valign="top" align="left">

- [Documentation](https://ramcodesbetter.github.io/SidewalkPilot/)
- [YouTube](https://www.youtube.com/@SidewalkPilot)
- [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat)
- [Parts List](https://1drv.ms/x/c/9685d41907cf4e28/IQAZPTqPm5FDRLypIrzf-Jv5AapVDVfyFpqjfn2W666oeXk?e=3MadEB)
- [Twitter](https://x.com/SidewalkPilot)
- [Email](mailto:ramsabavat2012@gmail.com)

</td>
<td valign="top" align="right">
<img src="docs/media/sidewalkpilot-demo.gif" alt="SidewalkPilot autonomous sidewalk-driving demonstration" width="300">
</td>
</tr>
</table>

> SidewalkPilot is a supervised research and learning project used on controlled test routes with the operator present. It is not certified or approved for unattended or public-road operation.

## Current Result

**SidewalkPilot v3.4** is the current field-selected steering model. During the July 13, 2026 comparison, v3.4 handled every shadow case presented and the tested normal left and right turns. v3.4b was slightly worse, v3.3 was worse than v3.2, and v3.3b was much worse than v3.2b. The observation is valuable but qualitative because route, clip, weather, and takeover metadata were not preserved.

I developed Series 3 and Series 4 on the same 81,237-image dataset snapshot. Series 4 tests whether recent steering targets or future-target supervision improve image-based steering prediction. The first v4.0 field comparison exposed a steering-echo failure in the PC and PCF models. The image-only v4.0f model was viable but did not clearly outperform v3.4. Six corrective v4.1 models have since been trained, evaluated offline, and added to the live selector; they are not yet field-tested.

| Experiment | Final epoch | Validation-selected epoch | Runtime contract |
|---|---|---|---|
| Previous + current (PC) | v4.0p | v4.0r | image + three prior steering targets -> current steering |
| Current + future (CF) | v4.0f | v4.0g | image -> current plus three future steering horizons |
| Previous + current + future (PCF) | v4.0a | v4.0c | image + three prior targets -> current plus three future horizons |

The six v4.0 ONNX models are supported by the live Jetson Orin Nano runtime and have been field-tested. The six v4.1 ONNX models retain the same three runtime contracts but still require integration and supervised physical testing. v3.4 remains the field-selected default.

## System Architecture

The three computers have separate responsibilities:

| Manager | Hardware | Responsibility |
|---|---|---|
| AI Model Manager | Jetson Orin Nano | Receives the newest camera frame over dedicated Ethernet and runs Series 1/2 through PyTorch CUDA or Series 3/4 through ONNX Runtime CUDA |
| Hardware and Safety Controller | Raspberry Pi 5 | Controller input, camera capture, LiDAR, GPS, steering, motors, logging, and final safety arbitration |
| Display Controller | Zero 2 W | Renders the Waveshare 64x32 HUB75 dashboard from UDP telemetry over a dedicated USB network |

The Jetson Orin Nano is essential to the current v3.4 and Series 4 self-driving path. Those
larger 320x180 models run too slowly on the Raspberry Pi 5 CPU for the selected live
deployment, while the Jetson Orin Nano GPU runs them near the camera rate. If no fresh
Jetson Orin Nano prediction is available, current autonomy stops. The Raspberry Pi 5 remains
the hardware and safety controller, so the Jetson Orin Nano never writes the servo or motors directly.
Manual driving can still operate without it, but camera-based autonomous steering requires a recent Jetson Orin Nano result for every model family.

<img src="docs/media/System_Architecture.jpg" alt="System architecture diagram" width="800">

The Jetson Orin Nano analyzes camera images in a background thread so the Raspberry Pi 5 can continue reading the controller and operating the car. LiDAR works as a separate braking system: it can slow or stop the car when an obstacle is directly ahead, but it does not swerve around the obstacle.

## Model Journey

SidewalkPilot has 52 evaluated steering checkpoints across four series:

- **Series 1:** compact 200x66 direct steering regression established the end-to-end image-to-servo loop.
- **Series 2:** retained the approximately 0.67-million-parameter model while testing data cleanup, steering range, and HSV/CLAHE preprocessing.
- **Series 3:** moved to 320x180 images and an approximately 5.53-million-parameter network. v3.1+ uses nine steering-class logits, nine class-local offsets, and one throttle output.
- **Series 4:** keeps the Series 3 visual backbone, removes throttle learning, and compares causal steering history and multi-horizon supervision. PC, CF, and PCF contain approximately 5.54M to 5.57M parameters.

The generated [steering-model report](docs/steering_model_report.pdf) evaluates all 52 checkpoints on the same frozen 6,952-frame challenge subset. Selection does not rely on MAE alone. The report includes balanced nine-class recall (Bal9), exact and adjacent turn recall, straight recall, median error, signed bias, and confusion matrices.

## Data and Training

Field runs record camera images paired with logical steering degrees (`0..180`) and absolute physical throttle (`0..1`). The current local Series 3/4 corpus contains 80,969 real-world images after 268 confirmed off-domain or duplicate frames were quarantined. Existing Series 3/4 checkpoints and the frozen evaluation report use the earlier 81,237-image snapshot. The trainer sorts images by path and groups them into 100-frame windows. Each window goes entirely into training or validation, which keeps most neighboring frames together. One capture run can still appear in both sets.

Training runs on an NVIDIA RTX 6000 Ada Generation GPU. The Series 3/4 trainers support lighting, color, flip, and synthetic-shadow augmentation. Each run preserves a final-epoch model and a validation-selected model, exports ONNX, and logs the run for comparison. Physical field testing remains the deciding factor after offline evaluation.

## Hardware

| Function | Component |
|---|---|
| AI Model Manager | Jetson Orin Nano |
| Hardware and Safety Controller | Raspberry Pi 5 |
| Display Controller | Zero 2 W |
| Chassis | Yahboom Ackermann 520M |
| Camera | Raspberry Pi Camera Module 3 Wide, full-field 2304x1296 sensor mode with 1280x720 output at a nominal 50 FPS (20 ms frame period) |
| Obstacle Detection (AEB) | Youyeetoo FHL-LD19 360-degree LiDAR through a CP2102 UART-to-USB Adapter; typical 10 Hz scans (100 ms per revolution) and 4,500 ranging points per second |
| Steering | PCA9685 Servo Controller at 50 Hz (20 ms period) and high-torque steering servo |
| Drive | Yahboom AT8236 Motor Controller and JGB37-520 DC motors (12 V, 550 RPM) |
| Navigation | BN880 GPS at its default 1 Hz fix rate (1,000 ms); onboard HMC5883L compass is bench-only (not used during runtime) |
| Motion feedback | Hall-effect wheel-speed sensor and external IMU |
| Manual control | Xbox Wireless Controller |
| Dashboard | Waveshare 64x32 HUB75 RGB LED matrix with nominal 10 Hz (100 ms) telemetry |

## Repository Map

| Path | Contents |
|---|---|
| `code/controller/current/` | Jetson Orin Nano inference server, Raspberry Pi 5 controller, and Zero 2 W dashboard runtime |
| `code/ai_models_datasets/series_1_and_2/` | Series 1/2 trainer and local dataset metadata |
| `code/ai_models_datasets/series_3_and_4/` | Series 3 trainer, six Series 4 training wrappers, and shared training code |
| `code/ai_models/` | Local/Hugging Face PTH and ONNX models; binaries are ignored by Git |
| `code/test_files/` | Model evaluation, hardware tests, and calibration tools |
| `docs/site/` | MkDocs documentation source |
| `docs/steering_model_report.pdf` | Generated 52-checkpoint evaluation report |

## License

Apache 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
