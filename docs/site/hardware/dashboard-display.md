# Dashboard Display

The display system is a Zero 2 W driving one Waveshare 64×32 RGB LED matrix through HUB75. The current renderer does not use a MAX7219 display.

## Software Boundary

| File | Responsibility |
|---|---|
| `code/controller/current/rc_car_app/hub75_dashboard.py` | Raspberry Pi 5 payload schema and UDP sender |
| `code/controller/current/z2w_dashboard.py` | Zero 2 W receiver, page state, bitmaps, and HUB75 rendering |
| `code/controller/current/8x8_bitmaps/` | Digits, letters, and signs |
| `code/rpi-rgb-led-matrix/` | Matrix driver/library |
| `code/test_files/display/hub75_rgbmatrix_test.py` | Panel color/glyph bench test |

The panel is fixed at 64×32 pixels and uses an 8×8 cell system for text pages. Camera view is downsampled to the full panel and serialized as RGB565. The LiDAR page uses raw pixels for guides, rungs, points, the car marker, and an 8×8 `C` glyph.

## Runtime Parameters

The receiver exposes matrix-driver settings for slowdown GPIO, row addressing, multiplexing, panel type, brightness, PWM bits, refresh limit, RGB sequence, and hardware pulse behavior. Deployed values belong in the Zero 2 W's systemd service rather than in page rendering code.

## Bench Test

1. Power the panel from its intended regulated supply; do not rely on Zero 2 W GPIO power.
2. Verify the HUB75 ribbon orientation and common ground.
3. Stop the dashboard service before running a direct matrix test.
4. Run the glyph/color test and check red, green, blue, white, alignment, and refresh stability.
5. Restart the dashboard service and verify all pages.

```bash
sudo systemctl stop sidewalkpilot-z2w-dashboard.service
sudo python code/test_files/display/hub75_rgbmatrix_test.py
sudo systemctl restart sidewalkpilot-z2w-dashboard.service
```

Wrong colors indicate `--led-rgb-sequence` or ribbon/panel configuration. Horizontal tearing or flicker indicates driver timing, power, or grounding before it indicates bad telemetry. `NO LINK` with a stable test pattern indicates the panel works and the fault is in USB/network/service state.

See [Dashboard Pages](../runtime-code/dashboard/pages.md) and [Zero 2 W Dashboard](../operations/zero-2w-dashboard.md).
