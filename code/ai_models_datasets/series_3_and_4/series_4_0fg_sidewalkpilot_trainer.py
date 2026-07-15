#!/usr/bin/env python3
"""Train experimental Series 4 CF: current target plus future-target supervision."""

from series_4_common import run_fixed_experiment


if __name__ == "__main__":
    run_fixed_experiment("4.0fg", "cf", "4.0f", "4.0g")
