# Dashboard Runtime

The Raspberry Pi 5 serializes current state in `hub75_dashboard.py`; `AsyncDashboardSender` keeps JSON encoding and socket work outside the 60 Hz control loop. The Zero 2 W receives UDP and renders the Waveshare 64x32 HUB75 panel with `z2w_dashboard.py`.

## Transport

| Setting | Live value |
|---|---|
| Route | USB Ethernet only |
| Raspberry Pi 5 | `192.168.10.1` |
| Zero 2 W | `192.168.10.2` |
| UDP port | `8765` |
| Nominal send rate | 10 Hz |
| Linked shutdown | Enabled |

The sender keeps one replaceable pending state. If the controller produces several updates before transmission, only the newest survives. Notifications use a small FIFO because they should not disappear when state changes. A successful UDP `sendto()` proves only local acceptance; receiver status, ping, and the physical display verify delivery.

## Payload

The JSON payload carries drive state, model name and inference rate, temperatures, navigation status, steering tuning, camera preview pixels, LiDAR points/action, and autonomy evidence. Values are clamped on both sender and receiver. Camera pixels are generated only for the camera page because they are the largest field. Every normal payload includes a timestamp; receiver freshness uses local packet-arrival time.

A shutdown object is sent repeatedly during controller cleanup to improve the chance of delivery over UDP.

## Pages and Controls

The display covers drive/PRND, steering/throttle/brake, steering and yaw tuning, model status, intervention evidence, temperatures, photo/camera status, navigation, GPS, camera preview, and LiDAR. Page IDs are intentionally sparse after old collection-countdown pages were removed. Right-stick axes move through the page grid; context-sensitive D-pad controls tune values, select models, or edit navigation.

The LiDAR page shows a center safety corridor and distance rungs. It does not display or command a left/right swerve policy.

## Link States and Recovery

- `NO LINK`: no controller packet arrived after receiver startup;
- `STALE`: packets arrived and then stopped;
- linked shutdown: an explicit shutdown payload exits and clears the panel;
- idle exit: optional receiver timeout after a previously active stream becomes silent.

`NO LINK` or `STALE` should be debugged in this order: controller process, receiver service and UDP listener, `usb0` carrier/address, bidirectional ping, then sender/receiver logs. Wi-Fi is not a telemetry fallback.

See [Computer Operations](../../operations/nvidia-pc.md) and [Bench Tests](../../testing/bench-tests/overview.md).
