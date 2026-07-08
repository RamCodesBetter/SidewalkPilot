# SidewalkPilot

A self-driving RC car for **sidewalks**. A camera-fed neural network steers a real four-wheeled car along residential sidewalks, with LiDAR emergency braking, GPS route-following, and a live LED dashboard — built on Raspberry Pi and NVIDIA Jetson.

🎥 [YouTube](https://www.youtube.com/@SidewalkPilot) · 📚 [Docs](https://ramcodesbetter.github.io/SidewalkPilot/) · 🤖 [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat) · 💻 [GitHub](https://github.com/RamCodesBetter/SidewalkPilot)

> Independent research/learning project, run on private test routes. Not a road-legal or production autonomous vehicle.

## How it works

Camera frames go to a CNN steering model running on a Jetson; its steering + throttle are arbitrated against LiDAR safety and GPS navigation, then written to the steering servo and drive motors. A Pi Zero 2 W renders live state on an LED matrix over USB.

```
Camera ─▶ Jetson (ONNX model) ─▶ steering + throttle ─┐
LiDAR  ─▶ emergency braking / obstacle avoidance ─────┼─▶ servo + motors
GPS    ─▶ route graph + A* navigation ────────────────┘
                          │
                          └─▶ LED dashboard (Pi Zero 2 W, USB)
```

## Hardware

| Part | Role |
|---|---|
| Raspberry Pi 5 | Main controller — sensors, motors, steering, logging |
| NVIDIA Jetson ("Jon") | Runs the steering model (ONNX / TensorRT) |
| Pi Zero 2 W | LED-matrix dashboard over USB |
| Camera (Picamera2) | Forward vision |
| LiDAR | Obstacle detection + automatic emergency braking |
| GPS + compass | Route following |
| PCA9685 + servo | Steering (DC motors drive; hall sensor measures speed) |
| Xbox controller | Manual drive + safety kill switch |

## The model

`SidewalkPilotV3` — a ~5.5M-parameter CNN with a **hybrid steering head**: it classifies a coarse steering bucket, then regresses the exact angle within it (plus a throttle output). Trained across three model series on tens of thousands of real sidewalk frames with shadow and lighting augmentation.

- **Current best: v3.2b** — ~14° mean absolute steering error on held-out validation. Full per-model breakdown in [`docs/steering_model_report.pdf`](docs/steering_model_report.pdf).
- Series 3 targets Jetson deployment with FP16 → INT8 / TensorRT acceleration.

## Repo layout

| Path | Contents |
|---|---|
| `code/controller/current/` | Live runtime — Pi controller, Jetson inference, dashboard |
| `code/ai_models_datasets/` | Training code + datasets (Series 1/2/3) |
| `code/ai_models/` | Trained model checkpoints |
| `code/test_files/` | Bench + calibration utilities |
| `docs/` | Model cards, evaluation report, MkDocs source |
| `trossachs_navigation_app/` | Companion iOS navigation app |

## License

Apache 2.0 — see [LICENSE](LICENSE).
