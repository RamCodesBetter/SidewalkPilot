#!/usr/bin/env python3
"""Train Series 4.1 PCF with robust history and future trajectory supervision."""

from series_4_common import run_fixed_experiment


if __name__ == "__main__":
    run_fixed_experiment(
        "4.1ac",
        "pcf",
        "4.1a",
        "4.1c",
        training_profile="history_future_robust",
    )
