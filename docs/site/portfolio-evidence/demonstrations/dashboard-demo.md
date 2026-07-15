# Dashboard Demo

The dashboard demonstration shows live vehicle telemetry on a physical 64x32 HUB75 panel driven by a Raspberry Pi Zero 2 W.

## What It Demonstrates

- The Pi queues latest-value UDP telemetry to an asynchronous sender targeting `192.168.10.2:8765` over the dedicated USB-Ethernet link.
- The Zero renders gear, speed, control values, model state, autonomy metrics, temperatures, photos, navigation, GPS, camera preview, and LiDAR state.
- `NO LINK` and `STALE` make transport failure visible instead of leaving apparently current values frozen on screen.
- The dashboard does not control the car; final control remains on the Pi.

## Current Page Grid

The visible grid contains 16 pages with sparse internal IDs up to `17`. The right stick moves vertically and horizontally through the grid. Current views include:

- Primary drive state and control values;
- Steering/yaw tuning and telemetry;
- Model prediction, confidence, and inference telemetry;
- Autonomy intervention statistics and device temperatures;
- Photo status;
- Navigation, GPS, and route state;
- 64x32 camera preview; and
- LiDAR scan with center-corridor guides and rungs.

The removed V3H2 and V3H3 collection-count pages are not part of the current grid.

## Evidence

- Pi sender: `code/controller/current/rc_car_app/hub75_dashboard.py`
- Zero renderer: `code/controller/current/z2w_dashboard.py`
- Link setup: `code/test_files/setup/install_usb_dashboard_link.sh`
- Pixel/layout tests: `code/test_files/display/test_z2w_lidar_layout.py`
