#!/usr/bin/env python3
"""
imu_yaw_test.py  –  Read the MG24 IMU stream and find the yaw axis

Run on the Pi after flashing mg24_yaw_firmware.ino to the XIAO MG24 Sense and
plugging it in over USB. It reads the gyro CSV (gx,gy,gz in deg/s) and shows
all three axes live, plus the biggest swing each has seen.

How to use it:
    1. python3 code/test_files/imu_yaw_test.py        # auto-finds /dev/ttyACM*
    2. Leave the car STILL  -> all three should sit near 0 (bias is zeroed).
    3. TURN THE CAR LEFT/RIGHT by hand. The axis whose number swings the MOST
       is YAW — that's the one the steering loop will use. (Should be Z if the
       board is mounted flat, but we confirm, not assume.)
    4. Tilt the car nose up/down and roll it side to side to see the OTHER two
       axes move — that confirms which is which.

Ctrl-C to quit; it prints which axis swung most.
"""

import argparse
import glob
import sys
import time

try:
    import serial  # pyserial
except ImportError:
    print("pyserial missing -> run:  pip install pyserial")
    raise SystemExit(1)


def find_port(explicit):
    if explicit:
        return explicit
    candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if not candidates:
        print("No /dev/ttyACM* or /dev/ttyUSB* found. Is the MG24 plugged in?")
        raise SystemExit(1)
    return candidates[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=None, help="serial port (default: first /dev/ttyACM*)")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    port = find_port(args.port)
    print(f"Opening {port} @ {args.baud} ...")
    ser = serial.Serial(port, args.baud, timeout=1.0)
    time.sleep(0.3)
    ser.reset_input_buffer()

    peak = [0.0, 0.0, 0.0]   # biggest |value| seen per axis
    labels = ("X", "Y", "Z")
    print("Reading. Keep still first (≈0), then TURN the car left/right.")
    print("(the axis that swings most = YAW)   Ctrl-C to stop.\n")

    try:
        while True:
            raw = ser.readline().decode("utf-8", "ignore").strip()
            if not raw or raw in ("READY",) or raw.startswith("ERR"):
                if raw:
                    print(f"  [{raw}]")
                continue
            parts = raw.split(",")
            if len(parts) != 3:
                continue
            try:
                gx, gy, gz = (float(p) for p in parts)
            except ValueError:
                continue
            vals = (gx, gy, gz)
            for i in range(3):
                if abs(vals[i]) > peak[i]:
                    peak[i] = abs(vals[i])
            # biggest current mover, for a live hint
            hot = labels[max(range(3), key=lambda i: abs(vals[i]))]
            print(f"\rX={gx:+7.1f}  Y={gy:+7.1f}  Z={gz:+7.1f} deg/s   "
                  f"moving:{hot}   peak X={peak[0]:.0f} Y={peak[1]:.0f} Z={peak[2]:.0f}   ",
                  end="", flush=True)
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

    yaw_axis = labels[max(range(3), key=lambda i: peak[i])]
    print(f"\n\nBiggest swing was on the {yaw_axis} axis "
          f"(X={peak[0]:.0f} Y={peak[1]:.0f} Z={peak[2]:.0f}).")
    print(f"If you were turning the car left/right, **{yaw_axis} is your YAW axis** "
          f"— tell me and I'll point the steering loop at it.")


if __name__ == "__main__":
    main()
