#!/usr/bin/env python3
"""Train experimental Series 4 PCF: previous targets -> current and future targets."""

from series_4_common import run_fixed_experiment


if __name__ == "__main__":
    run_fixed_experiment("4.0ac", "pcf", "4.0a", "4.0c")
