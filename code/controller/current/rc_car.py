#!/usr/bin/python3
"""RC car controller entrypoint.

Model selection remains on the dashboard. Steering inference runs on the Jetson
Orin Nano.
"""

from __future__ import annotations

import argparse


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=__doc__)


def main(argv: list[str] | None = None) -> None:
    _parser().parse_args(argv)
    from rc_car_app.runtime import run

    run()


if __name__ == "__main__":
    main()
