# SidewalkPilot

A self-driving RC car for **sidewalks**. A camera-fed neural network steers a real, car-sized RC vehicle down residential sidewalks — with LiDAR emergency braking, GPS route-following, and a live LED dashboard. Built from scratch on a Raspberry Pi 5 and an NVIDIA Jetson.

🎥 [YouTube](https://www.youtube.com/@SidewalkPilot) · 📚 [Docs](https://ramcodesbetter.github.io/SidewalkPilot/) · 🤖 [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat) · 💻 [GitHub](https://github.com/RamCodesBetter/SidewalkPilot)

> Independent research/learning project, run on private test routes. Not a road-legal or production autonomous vehicle.

## How it works

Three "manager" computers split the job. The **Raspberry Pi 5 (RPI5)** reads every sensor and drives the hardware. It streams camera frames to the **Jetson Orin Nano (JON)**, which runs the neural network and sends back a steering angle + throttle. The RPI5 then **fuses** that with LiDAR safety and GPS navigation before moving the wheels — and mirrors everything to a **Raspberry Pi Zero 2 W (Z2W)** LED dashboard.

```
   Camera 3 Wide ─┐
   360° LiDAR ────┤                       frames ──▶ ┌────────────────────────┐
   GPS + compass ─┼──▶  Raspberry Pi 5   ───────────▶│  Jetson Orin Nano (JON)│
   Hall sensor ───┘     (RPI5)                        │  "AI Model Manager"    │
   Xbox controller ─▶   "Major System   ◀────────────│  runs the steering CNN │
                         Manager"     steer + throttle└────────────────────────┘
                            │
          fuse:  model steering  +  LiDAR braking  +  GPS route
                            │
             ┌──────────────┼────────────────┐
             ▼              ▼                 ▼
      Steering servo    Drive motors    Pi Zero 2 W (Z2W)
       (PCA9685)         (AT8236)       LED dashboard
```

**Sense → Think → Act:** sensors feed the RPI5, the JON does the thinking, and the RPI5 acts on the wheels — with the human always able to grab the Xbox controller and take over or kill the run.

## Hardware

| Role | Component |
|---|---|
| **Major System Manager (RPI5)** | Raspberry Pi 5 (8 GB) — main controller: sensors, motors, steering, logging |
| **AI Model Manager (JON)** | NVIDIA Jetson Orin Nano Super — runs the steering neural network (ONNX / TensorRT) |
| **Display System Manager (Z2W)** | Raspberry Pi Zero 2 W — LED dashboard over USB |
| Vision | Raspberry Pi Camera Module 3 Wide |
| Obstacles | Youyeetoo FHL-LD19 360° LiDAR — emergency braking + avoidance |
| Navigation | BN880 GPS + HMC5883L compass |
| Speed | Hall-effect sensor |
| Chassis | Yahboom Ackermann 520M — real car-style steering |
| Steering | PCA9685 PWM driver → steering servo |
| Drive | Yahboom AT8236 motor controller → DC motors |
| Manual control | Xbox Wireless Controller — drive + safety kill switch |
| Dashboard | Waveshare 64×32 RGB LED matrix (HUB75) + MAX7219 8×32 |
| Power | INIU power banks (140 W for JON, 45 W for RPI5/Z2W); OVONIC 3S LiPo (motors) + 2S LiPo (display); buck converters + fuses |

## The model

The brain is a convolutional neural network trained on tens of thousands of real sidewalk frames. It has grown through three generations:

- **Series 1 — the foundation.** A small (~2.7 M-parameter) network that predicts a steering angle directly from the image (200×66 input). It proved a car could follow a sidewalk from camera alone, and established the image → steering-label training pipeline.
- **Series 2 — refinement.** Same direct-steering design, cleaner data, and tuned steering range. Added an HSV + CLAHE contrast option (models 2.0/2.0b) to fight harsh lighting — kept as a tool, not the default.
- **Series 3 — the current generation.** A larger (~5.5 M-parameter) network with a **hybrid head**: it first classifies a coarse steering direction, then regresses the exact angle within it (plus throttle), on a 320×180 image with shadow/lighting augmentation. Series 3 was *originally targeted for quantization* (FP32 → FP16 → INT8 / TensorRT) to squeeze a heavy model onto the Jetson — but the focus **shifted toward accuracy and robustness**: the hybrid head and shadow-hardened training, running directly on the Jetson Orin Nano Super.

Current best model **v3.2b** predicts steering to ~14° mean error on held-out validation — full per-model breakdown in [`docs/steering_model_report.pdf`](docs/steering_model_report.pdf).

## Repo layout

| Path | Contents |
|---|---|
| `code/controller/current/` | Live runtime — RPI5 controller, JON inference server, Z2W dashboard |
| `code/ai_models_datasets/` | Training code + datasets (Series 1/2/3) |
| `code/ai_models/` | Trained model checkpoints |
| `code/test_files/` | Bench + calibration utilities |
| `docs/` | Model cards, evaluation report, MkDocs source |
| `trossachs_navigation_app/` | Companion iOS navigation app |

## License

Apache 2.0 — see [LICENSE](LICENSE).
