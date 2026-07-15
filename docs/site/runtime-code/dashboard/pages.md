# Dashboard Pages

The controller owns the two-dimensional page grid in `DASHBOARD_PAGE_COORDS`; `DashboardRenderer` in `code/controller/current/z2w_dashboard.py` owns the pixels. Right-stick Y moves between vertical groups and right-stick X moves among pages in the current group.

| Grid | Internal ID | Rows or view |
|---|---:|---|
| V1H1 | 1 | Speed/PRND, run number, clock, odometer or alert |
| V1H2 | 2 | `SRVO`, `TTLE`, `BRKE`, `MODE` |
| V1H3 | 13 | Steering trim and yaw PID `kP/kI/kD` tuning |
| V1H4 | 15 | Yaw rate, speed, correction, input/output steering |
| V2H1 | 3 | Model, predicted servo angle, confidence, IPS |
| V2H2 | 4 | Intervention cause, autonomous distance, interventions/km, uptime |
| V2H3 | 16 | Pi, Jon CPU, Jon GPU, and Zero CPU temperatures |
| V3H1 | 14 | Photos this run, photos all-time, camera FPS, status |
| V4H1 | 5 | Navigation address entry |
| V4H2 | 7 | Route node state |
| V4H3 | 9 | Route distance state |
| V4H4 | 10 | Route time state |
| V5H1 | 6 | GPS fix, satellites, odometer, fix type |
| V5H2 | 8 | Latitude and longitude |
| V6H1 | 11 | 64×32 camera preview |
| V6H2 | 17 | LiDAR scan, center guides, distance rungs, `C` state |

Internal IDs are intentionally sparse because existing render functions retained their IDs. `DASHBOARD_PAGE_COUNT = 17` is the highest valid ID, not the number of visible pages.

## Removed Pages

`V3H2` and `V3H3` previously displayed steering-bucket collection countdowns. They were removed because capture-time bucket classification and persistent JSON writes added work unrelated to driving. The current dashboard does not transmit or parse `photo_run_stats`, and no page updates `collection_progress.json`.

## Page-Specific Controls

- V1H3: D-pad up/down selects trim or PID row; left/right changes it.
- V2H1: D-pad up/down cycles models.
- V4H1: D-pad edits the destination; X opens/starts/stops navigation.
- V6H2: display only. LiDAR never commands steering.

## Link States

- `NO LINK`: no controller payload arrived within three seconds of receiver startup.
- `STALE`: payloads were received, then stopped for four seconds.
- `GOOD`, `SAVE`, or `ERR`: current controller status on V3H1.

Pixel-level LiDAR/page checks run with:

```bash
python3 code/test_files/test_z2w_lidar_layout.py
```
