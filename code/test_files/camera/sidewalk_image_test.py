#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
CURRENT_CONTROLLER_DIR = PROJECT_ROOT / "code" / "controller" / "current"
if str(CURRENT_CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_CONTROLLER_DIR))

from rc_car_app.vision import annotate_sidewalk_edges, cv2, estimate_path_bias_from_frame


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_annotated{input_path.suffix}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the current sidewalk-edge detection method on one image and save an annotated result."
    )
    parser.add_argument("image", help="Path to the input image.")
    parser.add_argument(
        "--output",
        help="Path to the annotated output image. Defaults to <input>_annotated.<ext>.",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        help="Optional path to save the raw analysis JSON.",
    )
    return parser.parse_args()


def main():
    if cv2 is None:
        raise SystemExit("OpenCV is not available in this environment.")

    args = parse_args()
    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")

    frame = cv2.imread(str(image_path))
    if frame is None:
        raise SystemExit(f"Failed to read image: {image_path}")

    analysis = estimate_path_bias_from_frame(frame)
    annotated = annotate_sidewalk_edges(frame, analysis)

    output_path = Path(args.output).expanduser().resolve() if args.output else default_output_path(image_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(output_path), annotated)
    if not ok:
        raise SystemExit(f"Failed to write annotated image: {output_path}")

    print(f"Input image: {image_path}")
    print(f"Annotated image: {output_path}")
    print("Analysis:")
    print(json.dumps(analysis, indent=2))

    if args.json_output:
        json_path = Path(args.json_output).expanduser().resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(analysis, indent=2))
        print(f"Saved analysis JSON: {json_path}")


if __name__ == "__main__":
    main()
