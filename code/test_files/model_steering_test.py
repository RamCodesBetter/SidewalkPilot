#!/usr/bin/python3
import argparse
import sys
import time
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_CODE_DIR = CURRENT_DIR.parent
CONTROLLER_CURRENT_DIR = REPO_CODE_DIR / "controller" / "current"
if str(CONTROLLER_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_CURRENT_DIR))

from rc_car_app.vision import STEERING_MODEL_CHOICES, WebcamVisionProcessor
from rc_car_app.config import (
    ENABLE_HUB75_DASHBOARD_TELEMETRY,
    HUB75_DASHBOARD_BAUD_RATE,
    HUB75_DASHBOARD_HOST,
    HUB75_DASHBOARD_SEND_INTERVAL_SEC,
    HUB75_DASHBOARD_SERIAL_PORT,
    HUB75_DASHBOARD_TRANSPORT,
    HUB75_DASHBOARD_UDP_PORT,
)
from rc_car_app.hub75_dashboard import Hub75DashboardSender

LOG_INTERVAL_SEC = 0.25


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def parse_args():
    parser = argparse.ArgumentParser(description="Test model-predicted steering with motors off.")
    parser.add_argument(
        "--model",
        choices=tuple(STEERING_MODEL_CHOICES.keys()),
        default="1.0",
        help="Steering autonomy model to load from code/ai_models.",
    )
    parser.add_argument(
        "--no-servo",
        action="store_true",
        help="Only print predicted servo degrees; do not move the steering servo.",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Do not send predicted servo degrees to the HUB75 dashboard.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    hardware = None
    dashboard_sender = None
    if not args.no_servo:
        from rc_car_app.hardware import Hardware

        hardware = Hardware(lambda: None)
    if ENABLE_HUB75_DASHBOARD_TELEMETRY and not args.no_dashboard:
        dashboard_sender = Hub75DashboardSender(
            transport=HUB75_DASHBOARD_TRANSPORT,
            baud_rate=HUB75_DASHBOARD_BAUD_RATE,
            send_interval_sec=HUB75_DASHBOARD_SEND_INTERVAL_SEC,
            serial_port=HUB75_DASHBOARD_SERIAL_PORT,
            udp_host=HUB75_DASHBOARD_HOST,
            udp_port=HUB75_DASHBOARD_UDP_PORT,
        )
    webcam_vision = WebcamVisionProcessor(model_choice=args.model)
    if not webcam_vision.start():
        print("Failed to start camera vision.")
        if dashboard_sender:
            dashboard_sender.close()
        if hardware:
            hardware.cleanup()
        return 1

    print("Model steering test started.")
    print("Motors stay OFF. Only front steering servo moves.")
    print(f"Model: {args.model}")
    if dashboard_sender:
        print("Dashboard: page 2 SRVO row mirrors servo_deg predictions.")
    print("Press Ctrl+C to quit.")

    last_log_time = 0.0

    try:
        while True:
            analysis, last_frame_time = webcam_vision.get_analysis()
            method = analysis.get("method", "none")
            heading_bias = float(analysis.get("heading_bias", 0.0))
            confidence = float(analysis.get("confidence", 0.0))
            servo_degrees = float(analysis.get("steering_angle_deg", 90.0))

            if hardware:
                # Keep all drive motors off for this test.
                hardware.motor_left_fwd.value = 0
                hardware.motor_left_bwd.value = 0
                hardware.motor_right_fwd.value = 0
                hardware.motor_right_bwd.value = 0

            if method.startswith("SidewalkPilot:"):
                servo_degrees = clamp(servo_degrees, 0.0, 180.0)
            else:
                servo_degrees = 90.0

            if not args.no_servo:
                hardware.steering_servo.value = servo_degrees

            if dashboard_sender:
                dashboard_sender.send(
                    0.0,
                    "P",
                    False,
                    False,
                    "",
                    100,
                    dashboard_page=2,
                    servo_deg=servo_degrees,
                    throttle_percent=0,
                    brake_percent=0,
                    drive_mode="MAN",
                )

            now = time.time()
            if now - last_log_time >= LOG_INTERVAL_SEC:
                frame_age = max(0.0, now - last_frame_time)
                print(
                    f"method={method} conf={confidence:.3f} "
                    f"servo_deg={servo_degrees:.1f} "
                    f"heading_bias={heading_bias:.3f} age={frame_age:.2f}s"
                )
                last_log_time = now

            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        webcam_vision.stop()
        if dashboard_sender:
            dashboard_sender.close()
        if hardware:
            hardware.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
