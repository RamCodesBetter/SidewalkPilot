# Dashboard Payload Format

The Raspberry Pi 5 sends one compact JSON object per telemetry update. UDP sends one JSON object per datagram; serial mode sends the same object followed by a newline. The sender is `Hub75DashboardSender` and the receiver is `code/controller/current/z2w_dashboard.py`.

## Main Groups

| Group | Representative keys |
|---|---|
| Drive | `speed_mph`, `gear`, `servo_deg`, `throttle_percent`, `brake_percent`, `drive_mode` |
| Display | `dashboard_page`, `dashboard_page_transition`, `brightness_percent`, `dashboard_alert` |
| Model | `model_choice`, `camera_confidence_percent`, `infer_fps` |
| Temperatures | `cpu_temp_c`, `jon_cpu_temp_c`, `jon_gpu_temp_c` |
| LiDAR | `lidar_points`, `lidar_point_count`, center occupancy and action |
| Camera | 32 strings in `camera_pixels`, each encoding 64 RGB565 pixels |
| Photos | `photos_run`, `photos_all`, `camera_fps`, `system_status` |
| Navigation | nested `nav_status` object |
| Steering tuning | trim, PID gains, yaw rate, correction, and command fields |
| Autonomy evidence | cause code, distance, interventions/km, average uptime |

LiDAR occupancy is normalized to the single current lane identifier `C`. Historical L/R lane fields and `photo_run_stats` are not part of the current payload.

## Freshness and Shutdown

Every normal payload contains a Unix `timestamp`. Receiver freshness uses local arrival time rather than trusting clock synchronization. A separate payload:

```json
{"shutdown":true,"timestamp":0.0}
```

requests linked receiver shutdown. The sender transmits it repeatedly during controller cleanup to reduce UDP-loss risk.

## Limits

The sender clamps percentages to `0..100`, steering to `0..180`, temperatures and rates to displayable ranges, page IDs to `1..17`, model names to four characters, and LiDAR values to their display ranges. The receiver independently clamps again before rendering.

The camera preview is the largest payload field. It is generated only while the camera page is selected; otherwise the controller sends an empty list.

The exact schema is built in `Hub75DashboardSender.send()`. The last transmitted JSON is copied into the controller CSV as `dashboard_payload_json` for debugging.
