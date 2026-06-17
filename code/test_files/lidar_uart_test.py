#!/usr/bin/env python3
import argparse
import os
import time

import serial

try:
    from gpiozero import PWMOutputDevice
except Exception:
    PWMOutputDevice = None


def parse_args():
    parser = argparse.ArgumentParser(description="Direct SidewalkPilot GPIO UART LiDAR test")
    parser.add_argument("--port", default="/dev/ttyAMA3")
    parser.add_argument("--baud", type=int, default=230400)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--enable-gpio", type=int, default=18)
    parser.add_argument("--no-enable", action="store_true")
    return parser.parse_args()


def count_lidar_packets(buffer: bytes) -> int:
    packets = 0
    index = 0
    while index + 47 <= len(buffer):
        header_index = buffer.find(b"\x54\x2c", index)
        if header_index < 0:
            break
        if header_index + 47 <= len(buffer):
            packets += 1
        index = header_index + 47
    return packets


def main() -> int:
    args = parse_args()
    enable = None

    print(f"LiDAR UART test: port={args.port} baud={args.baud} seconds={args.seconds:g}")
    if os.path.exists(args.port):
        print(f"{args.port} exists.")
    else:
        print(f"{args.port} does not exist.")
        return 2

    if not args.no_enable:
        if PWMOutputDevice is None:
            print("gpiozero is unavailable; cannot drive LiDAR enable GPIO.")
        else:
            enable = PWMOutputDevice(args.enable_gpio, frequency=1000, initial_value=1.0)
            print(f"GPIO{args.enable_gpio} LiDAR enable held at 100%.")

    try:
        with serial.Serial(args.port, args.baud, timeout=0.1) as ser:
            start = time.monotonic()
            next_report = start + 1.0
            total_bytes = 0
            total_packets = 0
            sample = b""
            window = b""

            while time.monotonic() - start < args.seconds:
                chunk = ser.read(4096)
                if chunk:
                    total_bytes += len(chunk)
                    if not sample:
                        sample = chunk[:64]
                    window = (window + chunk)[-4096:]
                now = time.monotonic()
                if now >= next_report:
                    packets = count_lidar_packets(window)
                    total_packets += packets
                    window = b""
                    print(f"{now - start:5.1f}s  bytes={total_bytes}  packets+={packets}")
                    next_report += 1.0

            if window:
                total_packets += count_lidar_packets(window)

            print(f"TOTAL bytes={total_bytes} packets={total_packets}")
            if sample:
                print(f"FIRST_BYTES {sample.hex(' ')}")
            else:
                print("NO_BYTES_READ")
    finally:
        if enable is not None:
            enable.off()
            enable.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
