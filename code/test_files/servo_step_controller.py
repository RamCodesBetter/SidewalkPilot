#!/usr/bin/env python3
"""Headless Xbox-controlled PCA9685 servo step tester.

Run this on the Raspberry Pi over SSH with the Xbox controller connected. It
does not create a visible pygame window and does not drive the motors.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

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
    DASHBOARD_BRIGHTNESS_PERCENT_DEFAULT,
    HUB75_DASHBOARD_BAUD_RATE,
    HUB75_DASHBOARD_HOST,
    HUB75_DASHBOARD_SEND_INTERVAL_SEC,
    HUB75_DASHBOARD_SERIAL_PORT,
    HUB75_DASHBOARD_TRANSPORT,
    HUB75_DASHBOARD_UDP_PORT,
    PCA9685_FREQUENCY_HZ,
    PCA9685_I2C_ADDRESS,
    PCA9685_SERVO_CHANNEL,
    STEERING_SERVO_ACTUATION_RANGE_DEG,
    STEERING_SERVO_MAX_PULSE_US,
    STEERING_SERVO_MIN_PULSE_US,
)
from rc_car_app.hub75_dashboard import Hub75DashboardSender


A_BUTTON = 0
B_BUTTON = 1
X_BUTTON = 3
Y_BUTTON = 4
SHARE_BUTTON = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Step steering servo by 15 degrees with Xbox A button.")
    parser.add_argument("--min-angle", type=int, default=0, help="first servo angle")
    parser.add_argument("--max-angle", type=int, default=180, help="last servo angle")
    parser.add_argument("--step", type=int, default=15, help="angle step")
    parser.add_argument("--start", type=int, default=0, help="starting servo angle")
    parser.add_argument("--wrap", action="store_true", help="wrap from max angle back to min angle on A")
    parser.add_argument("--dashboard-page", type=int, default=1, help=argparse.SUPPRESS)
    return parser.parse_args()


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def build_angles(min_angle: int, max_angle: int, step: int) -> list[int]:
    if step <= 0:
        raise ValueError("--step must be positive")
    if max_angle < min_angle:
        raise ValueError("--max-angle must be >= --min-angle")
    values = list(range(int(min_angle), int(max_angle) + 1, int(step)))
    if not values or values[-1] != int(max_angle):
        values.append(int(max_angle))
    return values


def nearest_index(values: list[int], target: int) -> int:
    return min(range(len(values)), key=lambda index: abs(values[index] - target))


def init_servo():
    i2c = busio.I2C(board.SCL, board.SDA)
    kit = ServoKit(channels=16, i2c=i2c, address=PCA9685_I2C_ADDRESS, frequency=PCA9685_FREQUENCY_HZ)
    servo = kit.servo[PCA9685_SERVO_CHANNEL]
    servo.set_pulse_width_range(STEERING_SERVO_MIN_PULSE_US, STEERING_SERVO_MAX_PULSE_US)
    servo.actuation_range = STEERING_SERVO_ACTUATION_RANGE_DEG
    return servo


def init_joystick():
    pygame.display.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected.")
        raise SystemExit(1)
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Initialized joystick: {joystick.get_name()}")
    return joystick


def init_dashboard_sender() -> Hub75DashboardSender:
    return Hub75DashboardSender(
        transport=HUB75_DASHBOARD_TRANSPORT,
        baud_rate=HUB75_DASHBOARD_BAUD_RATE,
        send_interval_sec=min(0.05, float(HUB75_DASHBOARD_SEND_INTERVAL_SEC)),
        serial_port=HUB75_DASHBOARD_SERIAL_PORT,
        udp_host=HUB75_DASHBOARD_HOST,
        udp_port=HUB75_DASHBOARD_UDP_PORT,
    )


def send_dashboard(sender: Hub75DashboardSender, angle: int, dashboard_page: int) -> None:
    sender.send(
        speed_mph=0.0,
        gear="P",
        left_signal_visible=False,
        right_signal_visible=False,
        dashboard_alert="",
        brightness_percent=DASHBOARD_BRIGHTNESS_PERCENT_DEFAULT,
        dashboard_page=dashboard_page,
        dashboard_page_transition="",
        servo_deg=float(angle),
        throttle_percent=0,
        brake_percent=0,
        drive_mode="CAL",
        system_status="CAL",
        dashboard_row1_text=f"SERVO:{angle:03d}",
    )


def set_angle(servo, sender: Hub75DashboardSender, angle: int, dashboard_page: int) -> None:
    servo.angle = float(angle)
    print(f"SERVO:{angle:03d}")
    send_dashboard(sender, angle, dashboard_page)


def button_pressed(joystick, button: int, previous_buttons: dict[int, bool]) -> bool:
    pressed = joystick.get_numbuttons() > button and bool(joystick.get_button(button))
    edge = pressed and not previous_buttons.get(button, False)
    previous_buttons[button] = pressed
    return edge


def main() -> int:
    args = parse_args()
    try:
        angles = build_angles(args.min_angle, args.max_angle, args.step)
    except ValueError as exc:
        print(exc)
        return 1

    servo = init_servo()
    joystick = init_joystick()
    dashboard_sender = init_dashboard_sender()

    index = nearest_index(angles, int(clamp(args.start, angles[0], angles[-1])))
    set_angle(servo, dashboard_sender, angles[index], args.dashboard_page)

    print("Servo step controller")
    print("  A: next 15-degree value")
    print("  B: previous 15-degree value")
    print("  X: reset to first value")
    print("  Y: center near 90 degrees")
    print("  Share: quit")
    print("  Dashboard row 1: SERVO:###")

    previous_buttons = {
        A_BUTTON: False,
        B_BUTTON: False,
        X_BUTTON: False,
        Y_BUTTON: False,
        SHARE_BUTTON: False,
    }
    clock = pygame.time.Clock()

    try:
        while True:
            pygame.event.pump()

            if button_pressed(joystick, SHARE_BUTTON, previous_buttons):
                return 0
            if button_pressed(joystick, A_BUTTON, previous_buttons):
                if index < len(angles) - 1:
                    index += 1
                    set_angle(servo, dashboard_sender, angles[index], args.dashboard_page)
                elif args.wrap:
                    index = 0
                    set_angle(servo, dashboard_sender, angles[index], args.dashboard_page)
                else:
                    print(f"SERVO:{angles[index]:03d} END")
            if button_pressed(joystick, B_BUTTON, previous_buttons):
                if index > 0:
                    index -= 1
                    set_angle(servo, dashboard_sender, angles[index], args.dashboard_page)
            if button_pressed(joystick, X_BUTTON, previous_buttons):
                index = 0
                set_angle(servo, dashboard_sender, angles[index], args.dashboard_page)
            if button_pressed(joystick, Y_BUTTON, previous_buttons):
                index = nearest_index(angles, int(STEERING_SERVO_ACTUATION_RANGE_DEG / 2))
                set_angle(servo, dashboard_sender, angles[index], args.dashboard_page)

            send_dashboard(dashboard_sender, angles[index], args.dashboard_page)
            clock.tick(30)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"Servo I2C write failed: {exc}")
        return 2
    finally:
        dashboard_sender.close()
        try:
            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
