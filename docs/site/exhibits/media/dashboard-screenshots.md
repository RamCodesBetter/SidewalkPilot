# Dashboard Screenshots

This page collects stills of the SidewalkPilot live dashboard — the HUB75 LED matrix
driven by the Zero 2 W — and the captured camera frames that go with them. These
images are the proof that the telemetry and observability layer is real and readable
during a drive, not just a claim in a table.

## What the dashboard is

The Raspberry Pi 5 controller streams telemetry over USB Ethernet to a Zero 2 W,
which renders it on a small RGB LED dashboard. The transport is UDP-only by design:
Raspberry Pi 5 `usb0` is `192.168.10.1`, the Zero 2 W is `192.168.10.2`, and packets go to
`192.168.10.2:8765` about every 100 ms (`HUB75_DASHBOARD_SEND_INTERVAL_SEC = 0.1`).
The Raspberry Pi 5 side serializes the payload in `hub75_dashboard.py`; the Zero 2 W renders it in
`z2w_dashboard.py`. Because the display rows are tiny, every label is a short fixed
token.

The display uses a two-dimensional page grid with sparse internal IDs up to `17`, and the driver scrolls pages
with the controller stick. Page 1 is the primary drive view (speed, PRND gear, turn
signals, and a 4-character alert field); later pages cover LiDAR/clearance, camera
status, GPS/odometry, and the A* route (nodes, remaining distance-to-turn, and route
time). A screenshot set should show at least the primary page plus one nav/LiDAR page
so the full instrument cluster is documented.

## What each screenshot proves

| Field | What to record |
|---|---|
| Screenshot | File name or link |
| Page | Grid position and internal page ID |
| State shown | Speed, gear, AEB, LiDAR clearance, nav node, alert |
| Condition | Live drive, bench test, link-loss demo |
| Claim supported | What the still demonstrates |
| Privacy status | Raw / reviewed / cleared |

## Readable states worth capturing

These are real, code-backed states — good screenshot targets because they show the
system telling the truth about itself:

- **`NO LINK`** — the Zero 2 W display is alive but has not received a packet recently.
  This is the exact failure signature that made USB link reliability a whole
  workstream, so a still of it is genuine evidence, not a bug to hide.
- **Photo-capture status field** — the alert region cycles `GOOD` -> `CTRE`
  (capture in progress) -> `SAVE` on a good capture, or `ERR` on failure. This mirrors
  the `photo_status` state machine in `runtime.py` and ties a dashboard still to the
  photo-capture pipeline.
- **AEB state** — the LiDAR automatic-emergency-braking layer shows its enabled /
  triggered state, proving the safety layer is observable while it arbitrates over
  the model.
- **Nav / route pages** — remaining route distance and time, and the next route node,
  proving the A* navigation is live on the instrument cluster.

## Why screenshot the dashboard at all

Because observability is part of the safety story, not a nicety. AEB, LiDAR
disconnect behavior, manual override, and photo-capture status are all supposed to be
*visible* rather than buried behind convenience flags. A screenshot of the car
correctly showing `NO LINK`, an AEB trigger, or a capture `ERR` is stronger evidence
of an honest system than a screenshot where everything looks nominal.

## Status

- Screenshots are captured from the live HUB75 display and from bench runs.
- All stills are internal until a privacy pass (any house numbers, faces, or plates
  visible in a paired camera frame). Dashboard-only stills carry no personal data but
  still get the same review before external publishing.

## Related pages

- `exhibits/media/video-index.md`
- `exhibits/media/photo-index.md`
- `portfolio-evidence/claims-and-proof/reproducibility-claim.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
