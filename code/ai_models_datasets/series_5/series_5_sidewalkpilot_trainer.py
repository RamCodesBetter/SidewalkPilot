"""Single command for the four implemented Series 5 training recipes."""
import argparse
from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage="%(prog)s {5.A,5.B,5.C,5.E} [recipe options]")
    parser.add_argument("recipe", choices=("5.A", "5.B", "5.C", "5.E"))
    recipe = parser.parse_args(sys.argv[1:2]).recipe
    entry = Path(__file__).with_name(f"series_5_{recipe[-1]}_sidewalkpilot_trainer.py")
    sys.argv = [str(entry), *sys.argv[2:]]
    runpy.run_path(str(entry), run_name="__main__")
