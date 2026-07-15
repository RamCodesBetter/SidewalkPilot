# Dashboard Bench Test

The current dashboard is one Waveshare 64x32 HUB75 panel driven by the Raspberry Pi Zero 2 W. The earlier MAX7219 panel is no longer part of the live display.

## Direct Panel Test

Run on the Zero 2 W with the car stationary:

```bash
cd ~/rc_car_code
python3 code/test_files/display/display_panel_test.py --glyph-set digits
```

`display_panel_test.py` directly exercises the HUB75 wiring, patterns, and glyph headers without requiring UDP telemetry. It separates a panel/power fault from a USB-network or dashboard-receiver fault.

## Full Link Test

1. Confirm `usb0` is up on both computers.
2. Confirm Pi `192.168.10.1` can ping Zero `192.168.10.2`.
3. Start the Zero dashboard service or `dash` alias.
4. Start `car` on the Pi.
5. Confirm live values replace `NO LINK` and update without freezing.

## Interpretation

- Correct direct patterns but `NO LINK`: inspect the USB network, UDP port `8765`, and sender/receiver processes.
- No direct pattern: inspect HUB75 power, ground, signal wiring, and test dependencies.
- Frozen values: verify packets continue and that only one receiver owns UDP port `8765`.
