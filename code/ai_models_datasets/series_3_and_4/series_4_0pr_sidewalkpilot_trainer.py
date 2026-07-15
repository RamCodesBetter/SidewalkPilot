#!/usr/bin/env python3
"""Train experimental Series 4 PC: previous targets -> current target."""

from series_4_common import run_fixed_experiment


if __name__ == "__main__":
    run_fixed_experiment("4.0pr", "pc", "4.0p", "4.0r")
