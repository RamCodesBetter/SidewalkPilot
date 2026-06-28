#!/usr/bin/env python3
"""
imu_yaw_test.py  –  Read the MG24 IMU stream, filter the yaw rate

Reads the gyro CSV (gx,gy,gz deg/s) from the MG24 and shows the raw 3 axes plus
a FILTERED yaw value, so you can (a) confirm the yaw axis and (b) tune the noise
filter that the steering PID will reuse.

Filter chain on the yaw axis (Z by default):
  1. median-of-N   -> kills isolated spikes (a lone 20 among 0,1,2 -> ignored)
  2. EMA low-pass  -> smooths the small jitter   ema = a*median + (1-a)*ema
  3. soft deadband -> subtract the threshold: below it -> 0, just above -> near 0
                      (3.5->0.0, 3.6->0.1). Continuous, so no 0<->3.5 edge chatter.

Usage:
  python3 code/test_files/imu_yaw_test.py --port /dev/ttyAMA3
  # tune: --axis 2 (0=X,1=Y,2=Z) --median 5 --ema 0.3 --deadband 2.0
"""

import argparse
import collections
import glob
import math
import time

try:
    import serial  # pyserial
except ImportError:
    print("pyserial missing -> run:  pip install pyserial")
    raise SystemExit(1)


def find_port(explicit):
    if explicit:
        return explicit
    cands = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if not cands:
        print("No port given and no /dev/ttyACM*/ttyUSB* found. "
              "For the GPIO UART pass --port /dev/ttyAMA3")
        raise SystemExit(1)
    return cands[0]


def median(seq):
    s = sorted(seq)
    return s[len(s) // 2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=None, help="serial port (e.g. /dev/ttyAMA3 for the GPIO UART)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--axis", type=int, default=2, help="yaw axis index 0=X 1=Y 2=Z (default 2=Z)")
    ap.add_argument("--median", type=int, default=5, help="median window, odd, kills spikes (default 5)")
    ap.add_argument("--ema", type=float, default=0.3, help="EMA alpha 0..1, lower = smoother/laggier (default 0.3)")
    ap.add_argument("--deadband", type=float, default=3.5, help="soft deadband (deg/s): below it -> 0; above, the threshold is subtracted (default 3.5)")
    args = ap.parse_args()

    port = find_port(args.port)
    print(f"Opening {port} @ {args.baud}   yaw=axis{args.axis}  "
          f"median={args.median} ema={args.ema} deadband={args.deadband}")
    ser = serial.Serial(port, args.baud, timeout=1.0)
    time.sleep(0.3)
    ser.reset_input_buffer()

    med_buf = collections.deque(maxlen=max(1, args.median))
    ema = 0.0
    print("Reading. Still = filtered yaw should sit at 0.  Ctrl-C to stop.\n")

    try:
        while True:
            raw = ser.readline().decode("utf-8", "ignore").strip()
            if not raw or raw == "READY" or raw.startswith("ERR"):
                if raw:
                    print(f"  [{raw}]")
                continue
            parts = raw.split(",")
            if len(parts) != 3:
                continue
            try:
                vals = [float(p) for p in parts]
            except ValueError:
                continue

            yaw_raw = vals[args.axis]
            med_buf.append(yaw_raw)
            med = median(med_buf)                       # 1. spike kill
            ema = args.ema * med + (1.0 - args.ema) * ema  # 2. smooth
            # 3. SOFT deadband: subtract the threshold so it's continuous
            #    (3.5 -> 0.0, 3.6 -> 0.1) instead of jumping 0 -> 3.5 at the edge.
            yaw = math.copysign(max(0.0, abs(ema) - args.deadband), ema)

            print(f"\rraw X={vals[0]:+6.1f} Y={vals[1]:+6.1f} Z={vals[2]:+6.1f}   "
                  f"yaw_raw={yaw_raw:+6.1f}  ->  FILTERED={yaw:+6.1f} deg/s     ",
                  end="", flush=True)
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
