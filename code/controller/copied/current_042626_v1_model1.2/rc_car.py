#!/usr/bin/python3
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="RC car controller")
    parser.add_argument(
        "--model",
        choices=("1.0", "1.0b", "1.1", "1.1b", "1.2", "1.2b"),
        default="1.0",
        help="Steering autonomy model to load from code/ai_models.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    from rc_car_app.runtime import run

    run(model_choice=args.model)
