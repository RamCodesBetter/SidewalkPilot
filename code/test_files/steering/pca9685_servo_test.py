#!/usr/bin/env python3
import argparse
import time

import board
import busio
from adafruit_servokit import ServoKit

I2C_ADDRESS = 0x40
FREQUENCY_HZ = 50
MIN_PULSE_US = 1000
MAX_PULSE_US = 2000
ACTUATION_RANGE_DEG = 180


def parse_args():
    parser = argparse.ArgumentParser(description="Minimal PCA9685 servo movement test")
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=I2C_ADDRESS)
    parser.add_argument("--min-angle", type=float, default=0.0)
    parser.add_argument("--max-angle", type=float, default=180.0)
    parser.add_argument("--step", type=float, default=1.0)
    parser.add_argument("--delay", type=float, default=0.03)
    return parser.parse_args()


def main():
    args = parse_args()
    i2c = busio.I2C(board.SCL, board.SDA)
    kit = ServoKit(channels=16, i2c=i2c, address=args.address, frequency=FREQUENCY_HZ)
    servo = kit.servo[args.channel]
    servo.set_pulse_width_range(MIN_PULSE_US, MAX_PULSE_US)
    servo.actuation_range = ACTUATION_RANGE_DEG

    print(f"Testing PCA9685 address=0x{args.address:02x} channel={args.channel}")
    print(f"Sweeping from {args.min_angle} to {args.max_angle} by {args.step} until Ctrl-C")
    try:
        while True:
            angle = args.min_angle
            while angle <= args.max_angle:
                print(f"angle={angle:.1f}")
                servo.angle = angle
                time.sleep(args.delay)
                angle += args.step

            angle = args.max_angle
            while angle >= args.min_angle:
                print(f"angle={angle:.1f}")
                servo.angle = angle
                time.sleep(args.delay)
                angle -= args.step
    except KeyboardInterrupt:
        servo.angle = None
        print("done")


if __name__ == "__main__":
    main()
