# Hero Run Evidence Standard

This page defines what a future end-to-end hero-run artifact must contain. It does not claim that a complete, indexed hero clip and matching log are already published.

## What a Valid Clip Shows

1. The selected model version and live Jon inference state.
2. Camera-driven steering reaching the PCA9685 servo.
3. Forward motion through the AT8236 motor controller.
4. Live dashboard values over USB Ethernet.
5. The operator present with a connected controller and line of sight.
6. A matching CSV log for the run.

LiDAR does not steer around obstacles. With AEB enabled, it can reduce forward throttle in the center corridor or request a hard brake at the emergency boundary.

## Claim Boundary

A hero clip proves an integrated run under the recorded route, model, lighting, payload, and operator conditions. It does not prove unrestricted autonomy, a universal top speed, detection of every obstacle, or safe unsupervised operation.

The July 13 comparison selected v3.4 after the tested normal and shadow turn cases, but its exact clip and route metadata were not preserved here. Series 4 has no hero-run or field verdict yet.

## Evidence

- Matching video and `~/logs/log_*.csv` file, or the equivalent file under the configured `RC_CAR_LOG_DIR`.
- Model/version startup log.
- Dashboard view showing current state.
- Run notes describing route, light, AEB state, interventions, and limitations.
