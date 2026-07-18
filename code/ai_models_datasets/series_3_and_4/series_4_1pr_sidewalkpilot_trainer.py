#!/usr/bin/env python3
"""Train Series 4.1 PC with robust, bounded steering-motion history."""

from series_4_common import run_fixed_experiment


if __name__ == "__main__":
    run_fixed_experiment(
        "4.1pr",
        "pc",
        "4.1p",
        "4.1r",
        training_profile="history_robust",
    )
