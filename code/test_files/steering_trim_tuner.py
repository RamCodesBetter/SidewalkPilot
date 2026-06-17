#!/usr/bin/python3
"""Interactive steering trim tuner for the RC car.

Run this on the Raspberry Pi with the Xbox controller connected. It drives only
the steering servo, not the motors.
"""

import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

BASE_DIR = Path(__file__).resolve().parents[1]
CURRENT_DIR = BASE_DIR / "controller" / "current"
sys.path.insert(0, str(CURRENT_DIR))

try:
    import pygame
except Exception as exc:
    print(f"pygame unavailable: {exc}")
    raise SystemExit(1)

try:
    import board
    import busio
    from adafruit_servokit import ServoKit
except Exception as exc:
    print(f"PCA9685 servo dependencies unavailable: {exc}")
    raise SystemExit(1)

from rc_car_app.config import (
    PCA9685_FREQUENCY_HZ,
    PCA9685_I2C_ADDRESS,
    PCA9685_SERVO_CHANNEL,
    STEERING_SERVO_ACTUATION_RANGE_DEG,
    STEERING_SERVO_MAX_PULSE_US,
    STEERING_SERVO_MIN_PULSE_US,
)


DEFAULT_START_ANGLE_DEG = 90.0
DEFAULT_STEP_DEG = 1.0
QUIT_BUTTON = 15
RESET_BUTTON = 1
PRINT_BUTTON = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune steering center with the D-pad.")
    parser.add_argument("--start", type=float, default=DEFAULT_START_ANGLE_DEG, help="starting servo angle")
    parser.add_argument("--step", type=float, default=DEFAULT_STEP_DEG, help="D-pad trim step in degrees")
    parser.add_argument("--min-angle", type=float, default=0.0, help="minimum servo angle")
    parser.add_argument(
        "--max-angle",
        type=float,
        default=float(STEERING_SERVO_ACTUATION_RANGE_DEG),
        help="maximum servo angle",
    )
    return parser.parse_args()


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def print_trim(angle_deg: float) -> None:
    center_deg = float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    delta_deg = angle_deg - center_deg
    center_offset = delta_deg / center_deg if center_deg else 0.0
    print(
        f"trim={angle_deg:.1f} deg "
        f"(delta {delta_deg:+.1f} deg, suggested STEERING_SERVO_CENTER_OFFSET={center_offset:+.4f})"
    )


def init_servo():
    i2c = busio.I2C(board.SCL, board.SDA)
    kit = ServoKit(channels=16, i2c=i2c, address=PCA9685_I2C_ADDRESS, frequency=PCA9685_FREQUENCY_HZ)
    servo = kit.servo[PCA9685_SERVO_CHANNEL]
    servo.set_pulse_width_range(STEERING_SERVO_MIN_PULSE_US, STEERING_SERVO_MAX_PULSE_US)
    servo.actuation_range = STEERING_SERVO_ACTUATION_RANGE_DEG
    return servo


def init_joystick():
    pygame.init()
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected.")
        raise SystemExit(1)
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Initialized joystick: {joystick.get_name()}")
    return joystick


def main() -> int:
    args = parse_args()
    if args.max_angle <= args.min_angle:
        print("--max-angle must be greater than --min-angle")
        return 1

    servo = init_servo()
    init_joystick()

    start_angle = clamp(args.start, args.min_angle, args.max_angle)
    angle = start_angle
    step = max(0.1, abs(args.step))
    servo.angle = angle

    print("Steering trim tuner")
    print("  D-pad left/right: adjust trim by 1 degree")
    print("  B: reset to 90 degrees")
    print("  A: print suggested config offset")
    print("  Share: quit")
    print_trim(angle)

    clock = pygame.time.Clock()
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 0
                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == QUIT_BUTTON:
                        return 0
                    if event.button == RESET_BUTTON:
                        angle = clamp(DEFAULT_START_ANGLE_DEG, args.min_angle, args.max_angle)
                        servo.angle = angle
                        print_trim(angle)
                    elif event.button == PRINT_BUTTON:
                        print_trim(angle)
                elif event.type == pygame.JOYHATMOTION:
                    hat_x, _ = event.value
                    if hat_x == -1:
                        angle = clamp(angle - step, args.min_angle, args.max_angle)
                        servo.angle = angle
                        print_trim(angle)
                    elif hat_x == 1:
                        angle = clamp(angle + step, args.min_angle, args.max_angle)
                        servo.angle = angle
                        print_trim(angle)
            clock.tick(30)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"Servo I2C write failed: {exc}")
        return 2
    finally:
        try:
            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
