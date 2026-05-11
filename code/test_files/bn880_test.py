#!/usr/bin/env python3
"""
BN-880 test: GPS (lat/long via UART) + compass heading (QMC5883L via I2C).

Wiring used:
  5V   -> 5V
  GND  -> GND
  SDA  -> SDA0 (GPIO 0, pin 27)  -- I2C0 bus 0
  SCL  -> SCL0 (GPIO 1, pin 28)
  TXD  -> RXD  (GPIO 15, pin 10) -- /dev/ttyAMA0
  RXD  -> TXD  (GPIO 14, pin 8)

Run: python3 bn880_test.py
"""

import serial
import smbus2
import math
import time
import threading

# ── Config ─────────────────────────────────────────────────────────────────
GPS_PORT   = "/dev/ttyAMA0"
GPS_BAUD   = 9600
I2C_BUS    = 1          # SDA0/SCL0 on Pi 5 = I2C bus 1
QMC_ADDR   = 0x1E       # HMC5883L/QMC5883L on this board

# Calibration offsets — run with --calibrate to compute, then paste results here
HARD_IRON_X = 71.5
HARD_IRON_Y = -86.0
SOFT_IRON_SCALE_Y = 1.0375

# Correction table: (raw_heading, true_heading) pairs from cardinal measurements
# Interpolates between known points to correct for soft-iron distortion
_CORRECTION = [
    (  2.6,   0.0),
    (103.7,  90.0),
    (190.8, 180.0),
    (279.3, 270.0),
    (362.6, 360.0),  # wrap: 360 + 2.6
]

def _apply_correction(raw):
    """Interpolate correction table to map raw heading to true heading."""
    for i in range(len(_CORRECTION) - 1):
        r0, t0 = _CORRECTION[i]
        r1, t1 = _CORRECTION[i + 1]
        if r0 <= raw <= r1:
            frac = (raw - r0) / (r1 - r0)
            return (t0 + frac * (t1 - t0)) % 360.0
    return raw

# HMC5883L registers
QMC_DATA   = 0x03       # X_MSB, X_LSB, Z_MSB, Z_LSB, Y_MSB, Y_LSB
QMC_CTRL1  = 0x00       # Config A
QMC_CTRL2  = 0x01       # Config B
QMC_MODE   = 0x02       # Mode register

# ── Shared state ────────────────────────────────────────────────────────────
gps_state = {"lat": None, "lon": None, "fix": False, "sats": 0, "alt": None}

# ── GPS thread ──────────────────────────────────────────────────────────────
def parse_nmea_gga(line):
    """Parse $GPGGA or $GNGGA and update gps_state."""
    try:
        parts = line.strip().split(',')
        if len(parts) < 10:
            return
        if parts[6] == '0' or parts[6] == '':
            gps_state["fix"] = False
            return
        def dm_to_dd(dm, hemi):
            if not dm:
                return None
            dot = dm.index('.')
            deg = float(dm[:dot-2])
            mins = float(dm[dot-2:])
            dd = deg + mins / 60.0
            if hemi in ('S', 'W'):
                dd = -dd
            return dd
        gps_state["lat"]  = dm_to_dd(parts[2], parts[3])
        gps_state["lon"]  = dm_to_dd(parts[4], parts[5])
        gps_state["fix"]  = True
        gps_state["sats"] = int(parts[7]) if parts[7] else 0
        gps_state["alt"]  = float(parts[9]) if parts[9] else None
    except Exception:
        pass

def gps_thread():
    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUD, timeout=1)
        print(f"GPS: connected on {GPS_PORT} @ {GPS_BAUD}")
    except Exception as e:
        print(f"GPS: failed to open {GPS_PORT}: {e}")
        return
    while True:
        try:
            line = ser.readline().decode('ascii', errors='ignore')
            if line.startswith(('$GPGGA', '$GNGGA')):
                parse_nmea_gga(line)
        except Exception:
            pass

# ── Compass ─────────────────────────────────────────────────────────────────
def init_qmc(bus):
    # Config A: 8 samples averaged, 15Hz, normal measurement
    bus.write_byte_data(QMC_ADDR, QMC_CTRL1, 0x70)
    # Config B: gain 1090 LSB/Gauss (default)
    bus.write_byte_data(QMC_ADDR, QMC_CTRL2, 0x20)
    # Mode: continuous measurement
    bus.write_byte_data(QMC_ADDR, QMC_MODE, 0x00)

def read_heading(bus):
    data = bus.read_i2c_block_data(QMC_ADDR, QMC_DATA, 6)
    def s16(msb, lsb):
        v = (msb << 8) | lsb
        return v - 65536 if v > 32767 else v
    # HMC5883L order: X_MSB, X_LSB, Z_MSB, Z_LSB, Y_MSB, Y_LSB
    x = s16(data[0], data[1])
    y = s16(data[4], data[5])
    heading = math.degrees(math.atan2((y - HARD_IRON_Y) * SOFT_IRON_SCALE_Y, -(x - HARD_IRON_X)))
    if heading < 0:
        heading += 360.0
    heading = (heading + 180.0 - 30.0) % 360.0
    return _apply_correction(heading)

# ── Calibration ─────────────────────────────────────────────────────────────
def calibrate():
    """
    Slowly rotate the car/sensor through at least one full 360° circle.
    Collects X/Y samples, finds min/max, computes hard-iron offsets.
    Keep the sensor flat and away from other metal during calibration.
    """
    try:
        bus = smbus2.SMBus(I2C_BUS)
        init_qmc(bus)
    except Exception as e:
        print(f"Cannot open compass: {e}")
        return

    print("Hard-iron calibration")
    print("Slowly rotate the sensor through a full 360° circle (keep it flat).")
    print("Press Ctrl+C when done.\n")

    x_min = x_max = y_min = y_max = None
    samples = 0

    try:
        while True:
            data = bus.read_i2c_block_data(QMC_ADDR, QMC_DATA, 6)
            def s16(msb, lsb):
                v = (msb << 8) | lsb
                return v - 65536 if v > 32767 else v
            x = s16(data[0], data[1])
            y = s16(data[4], data[5])

            x_min = x if x_min is None else min(x_min, x)
            x_max = x if x_max is None else max(x_max, x)
            y_min = y if y_min is None else min(y_min, y)
            y_max = y if y_max is None else max(y_max, y)
            samples += 1

            offset_x = (x_max + x_min) / 2.0
            offset_y = (y_max + y_min) / 2.0
            print(f"\r  samples={samples:4d}  x=[{x_min:6d},{x_max:6d}]  y=[{y_min:6d},{y_max:6d}]"
                  f"  offset=({offset_x:.1f}, {offset_y:.1f})", end='', flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass

    offset_x = (x_max + x_min) / 2.0
    offset_y = (y_max + y_min) / 2.0
    print(f"\n\nCalibration complete ({samples} samples)")
    print(f"\nPaste these values into bn880_test.py:\n")
    print(f"  HARD_IRON_X = {offset_x:.1f}")
    print(f"  HARD_IRON_Y = {offset_y:.1f}")
    x_range = x_max - x_min
    y_range = y_max - y_min
    print(f"  SOFT_IRON_SCALE_Y = {x_range:.1f} / {y_range:.1f}  # = {x_range/y_range:.4f}")


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    # Start GPS thread
    t = threading.Thread(target=gps_thread, daemon=True)
    t.start()

    # Init compass
    try:
        bus = smbus2.SMBus(I2C_BUS)
        init_qmc(bus)
        compass_ok = True
        print(f"Compass: QMC5883L found on I2C bus {I2C_BUS} addr 0x{QMC_ADDR:02X}")
    except Exception as e:
        bus = None
        compass_ok = False
        print(f"Compass: failed to init QMC5883L: {e}")

    print("\nReading — Ctrl+C to stop\n")
    print(f"{'Lat':>12}  {'Lon':>13}  {'Alt(m)':>7}  {'Sats':>4}  {'Heading':>9}  Fix")
    print("-" * 65)

    while True:
        heading_str = "---.-°"
        if compass_ok:
            try:
                h = read_heading(bus)
                heading_str = f"{h:6.1f}°"
            except Exception as e:
                heading_str = "  err "
                print(f"Compass error: {e}")

        g = gps_state
        lat_str = f"{g['lat']:12.7f}" if g['lat'] is not None else f"{'---':>12}"
        lon_str = f"{g['lon']:13.7f}" if g['lon'] is not None else f"{'---':>13}"
        alt_str = f"{g['alt']:7.1f}" if g['alt'] is not None else f"{'---':>7}"
        fix_str = f"YES ({g['sats']} sats)" if g['fix'] else "NO (waiting...)"

        print(f"{lat_str}  {lon_str}  {alt_str}  {g['sats']:>4}  {heading_str:>9}  {fix_str}")
        time.sleep(0.5)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--calibrate', action='store_true', help='Run hard-iron calibration')
    args = ap.parse_args()
    try:
        if args.calibrate:
            calibrate()
        else:
            main()
    except KeyboardInterrupt:
        print("\nStopped.")
