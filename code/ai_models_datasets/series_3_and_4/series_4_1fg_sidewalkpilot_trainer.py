#!/usr/bin/env python3
"""Train Series 4.1 CF with current-dominant future trajectory supervision."""

from series_4_common import run_fixed_experiment


if __name__ == "__main__":
    run_fixed_experiment(
        "4.1fg",
        "cf",
        "4.1f",
        "4.1g",
        training_profile="future_trajectory",
    )
