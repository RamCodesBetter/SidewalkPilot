#!/usr/bin/python3
import argparse

from rc_car_app.vision import STEERING_MODEL_CHOICES


def parse_args():
    parser = argparse.ArgumentParser(description="RC car controller")
    parser.add_argument(
        "--model",
        choices=tuple(STEERING_MODEL_CHOICES.keys()),
        default="1.0",
        help="Steering autonomy model to load from code/ai_models.",
    )
    parser.add_argument(
        "--no-lidar",
        action="store_true",
        help="Run without starting or reading the LiDAR hardware.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    from rc_car_app.runtime import run

    run(model_choice=args.model, enable_lidar=not args.no_lidar)
