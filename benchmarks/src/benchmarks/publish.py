# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Publish retained benchmark results without rerunning measurements."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence
from pathlib import Path

from benchmarks.config.benchmark import parse_duration_seconds
from benchmarks.results.publication import publication_jobs, publish_results


def main(argv: Sequence[str] | None = None) -> None:
    """Upload pending W&B runs selected by result, sweep, or experiment directory."""
    parser = argparse.ArgumentParser(
        prog="foretoken publish",
        description="Publish saved W&B results without sending requests to a model service.",
    )
    parser.add_argument(
        "directories", nargs="+", type=Path, metavar="RESULT_DIR",
        help="result, sweep, or experiment directories recorded with --output wandb",
    )
    parser.add_argument(
        "--timeout", type=parse_duration_seconds, default="10min", metavar="DURATION",
        help="total upload time budget, e.g. 10min or 1h (default: %(default)s)",
    )
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not math.isfinite(arguments.timeout) or arguments.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    try:
        jobs = publication_jobs(tuple(arguments.directories))
        if not jobs:
            raise ValueError("No saved W&B publications found; record results with --output wandb")
        if not publish_results(jobs, timeout=arguments.timeout):
            raise SystemExit(1)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
