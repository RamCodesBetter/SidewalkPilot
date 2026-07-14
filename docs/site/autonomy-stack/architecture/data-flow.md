# Runtime Data Flow

SidewalkPilot separates hardware ownership, inference, display, and safety so a slow secondary computer cannot directly stall actuator control.

```text
Xbox controller ─┐
Pi Camera ───────┤
LiDAR UART ──────┤
GPS/compass ─────┤→ Raspberry Pi 5 arbitration → PCA9685 steering + AT8236 drive
Hall sensor ─────┤             │
USB IMU ─────────┘             ├→ UDP/USB Ethernet → Zero 2 W → HUB75 display
                               └→ JPEG/TCP/Ethernet → Jetson ONNX → cached steering
```

## Raspberry Pi 5

The Pi 5 is the only computer that writes steering, motor, and brake hardware. It reads the Xbox controller, sensors, and latest Jon result, then applies gear, manual takeover, AEB, model freshness, yaw correction, and servo limits.

## Jetson Orin Nano

Jon receives the newest camera frame and requested model version over the private Ethernet link at `10.42.0.2:8770`. It returns steering, unused model throttle, temperatures, inference timing, and nine hybrid-bucket probabilities. It does not command GPIO directly.

## Zero 2 W

The Zero receives JSON telemetry at `192.168.10.2:8765` over USB Ethernet and renders the HUB75 panel. Dashboard failure does not stop the Pi control loop. Linked shutdown is explicit application behavior, not control authority.

## Safety Arbitration

1. Quit/manual takeover and gear state define whether motion is permitted.
2. Servo/model freshness faults can stop motion.
3. With AEB enabled, center-corridor emergency occupancy hard-brakes.
4. LiDAR slowdown caps requested forward throttle.
5. Camera/Jon provides autonomous steering only.
6. Manual or autonomous throttle reaches motor mapping only after these gates.

LiDAR does not select a path or output steering. Side returns are telemetry because empty space beside an obstacle is not proof of sidewalk.

## Timing Boundary

Camera, LiDAR, GPS, IMU, Jetson transport, dashboard transport, photo writes, and telemetry use workers or cached snapshots. The 60 Hz runtime loop consumes those snapshots. See [Runtime Loop](../../runtime-code/runtime-loop.md) for ownership and stall diagnostics.
