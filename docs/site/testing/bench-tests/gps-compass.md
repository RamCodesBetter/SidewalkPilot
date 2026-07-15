# GPS Compass

The GPS/compass bench test checks whether the BN-880 module reports a plausible position fix and magnetometer heading. It runs `code/test_files/sensors/bn880_test.py`, which reads the GPS over UART and the magnetometer over I2C in parallel and prints latitude, longitude, altitude, satellite count, and corrected heading. The live route manager currently consumes GPS fixes only; passing this compass test does not make compass heading an active navigation input.

## How it works

- GPS: a background thread opens `/dev/ttyAMA0` at `9600` baud, reads NMEA, and parses `$GPGGA` / `$GNGGA` sentences into decimal-degree lat/lon plus fix status, satellite count, and altitude.
- Compass: the HMC5883L/QMC5883L magnetometer on the BN-880 is read over I2C (bus `1`, address `0x1E`). Raw X/Y are corrected with hard-iron offsets (`HARD_IRON_X`, `HARD_IRON_Y`) and a soft-iron Y scale, then heading is computed with `atan2` and passed through a small interpolation table that maps measured raw headings to true cardinal headings.
- A `--calibrate` mode runs a separate routine: you slowly rotate the sensor through a full flat 360-degree circle while it tracks X/Y min/max, then it prints the hard-iron offsets and soft-iron scale to paste back into the script.
- The main loop prints a row about twice a second: `Lat`, `Lon`, `Alt(m)`, `Sats`, `Heading`, and a `Fix` column showing `YES (n sats)` or `NO (waiting...)`.

## Command

Run on the Raspberry Pi 5:

```bash
# live GPS + heading table
python3 code/test_files/sensors/bn880_test.py

# hard-iron calibration (rotate slowly through 360 degrees, flat, away from metal)
python3 code/test_files/sensors/bn880_test.py --calibrate
```

## Pass / warn / fail

- Pass: outdoors with sky view, `Fix` flips to `YES` with a sane satellite count and stable lat/lon; heading tracks the true direction the car points after calibration.
- Warn: fix is slow or the compass reads offset from true north — recalibrate hard/soft iron and keep the sensor away from motors and metal.
- Fail: permission-denied or no data on `/dev/ttyAMA0` (do not confuse it with the former LiDAR GPIO-UART path), or an I2C error at `0x1E` — fix the port/bus before trusting navigation.

## Why it matters

- Navigation can snap a GPS fix onto the sidewalk route graph. The corrected compass heading printed here is diagnostic evidence for future heading integration, not a value currently consumed by `navigation.py`.
- Compass distortion is the usual failure, so the built-in hard/soft-iron calibration and the raw-to-true correction table are part of the test, not an afterthought.

## Evidence to attach

- The live table with a `YES` fix and satellite count
- Calibration output (the printed offsets and soft-iron scale)
- A note comparing reported heading to true north at a few cardinal points

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
