# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Weights & Biases logging for per-request benchmark history."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

import wandb

from benchmarks.config import BenchConfig, WandbConfig

logger = logging.getLogger(__name__)

_SYSTEM_STATS_INTERVAL_S = 1.0
_TIME_TAKEN = "Test Duration"
_CONCURRENCY = "Concurrency"
_REQUEST_RATE = "Request Rate"
_TOTAL_REQUESTS = "Total Requests"
_SUCCEED_REQUESTS = "Success Requests"
_FAILED_REQUESTS = "Failed Requests"
_REQUEST_THROUGHPUT = "Request Throughput"
_AVERAGE_LATENCY = "Avg Latency"
_AVERAGE_INPUT_TOKENS = "Avg Input Tokens"
_OUTPUT_TOKEN_THROUGHPUT = "Output Throughput"
_TOTAL_TOKEN_THROUGHPUT = "Total Throughput"
_AVERAGE_TTFT = "Avg TTFT"
_AVERAGE_TPOT = "Avg TPOT"
_AVERAGE_ITL = "Avg ITL"
_AVERAGE_OUTPUT_TOKENS = "Avg Output Tokens"


def wandb_timestamp() -> str:
    """Return ``YYYYMMDD_HHMMSS`` for W&B names / groups."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def wandb_run_base(config: BenchConfig) -> str:
    """Name/group base: ``--wandb-run-name`` if set, else ``{model}_{time}``."""
    run_name = config.wandb.run_name.strip()
    if run_name:
        return run_name
    return f"{config.endpoint.model}_{wandb_timestamp()}"


def running_to_wandb_message(
    results: list[dict[str, Any]],
    *,
    parallel: int,
    rate: float,
) -> dict[str, Any]:
    """Aggregate ``results[:step+1]`` into W&B chart keys for one history step."""
    success = [result for result in results if result["success"]]
    n_success = len(success)
    elapsed = max(float(result["end_time"]) for result in results)
    out_tokens = sum(int(result["output_tokens"]) for result in success)
    in_tokens = sum(int(result["input_tokens"]) for result in success)
    tpot_ms = round(
        sum(float(result["tpot"]) for result in success) / n_success * 1000.0, 2
    )
    return {
        _TIME_TAKEN: round(elapsed, 4),
        _CONCURRENCY: int(parallel),
        _REQUEST_RATE: float(rate),
        _TOTAL_REQUESTS: len(results),
        _SUCCEED_REQUESTS: n_success,
        _FAILED_REQUESTS: len(results) - n_success,
        _REQUEST_THROUGHPUT: round(len(results) / elapsed, 4),
        _OUTPUT_TOKEN_THROUGHPUT: round(out_tokens / elapsed, 4),
        _TOTAL_TOKEN_THROUGHPUT: round((in_tokens + out_tokens) / elapsed, 4),
        _AVERAGE_INPUT_TOKENS: round(in_tokens / n_success, 4),
        _AVERAGE_OUTPUT_TOKENS: round(out_tokens / n_success, 4),
        _AVERAGE_LATENCY: round(
            sum(float(result["latency"]) for result in success) / n_success, 4
        ),
        _AVERAGE_TTFT: round(
            sum(float(result["ttft"]) for result in success) / n_success * 1000.0, 2
        ),
        _AVERAGE_TPOT: tpot_ms,
        _AVERAGE_ITL: tpot_ms,
    }


class WandbLogger:
    """Optional W&B session: one history step per request."""

    def __init__(self) -> None:
        self._active = False

    @property
    def enabled(self) -> bool:
        return self._active

    def start(
        self,
        config: BenchConfig,
        *,
        output_dir: str,
        parallel: int,
        rate: float,
        name_suffix: Optional[str] = None,
        group: Optional[str] = None,
    ) -> None:
        """Initialize W&B when selected as a result destination."""
        wandb_config: WandbConfig = config.wandb
        if not config.output.includes("wandb"):
            return

        os.makedirs(output_dir, exist_ok=True)
        os.environ["WANDB_SILENT"] = "true"
        os.environ["WANDB_DIR"] = output_dir
        base = group or wandb_run_base(config)
        name = f"{base}_{name_suffix}" if name_suffix else base
        init_kwargs: dict[str, Any] = {
            "project": wandb_config.project,
            "name": name,
            "config": config.to_dict(),
            "dir": output_dir,
            "settings": wandb.Settings(
                x_stats_sampling_interval=_SYSTEM_STATS_INTERVAL_S
            ),
        }
        if group:
            init_kwargs["group"] = group
        if wandb_config.entity:
            init_kwargs["entity"] = wandb_config.entity
        wandb.init(**init_kwargs)
        self._active = True
        logger.info(
            "W&B logging enabled: project=%s name=%s group=%s concurrency=%s rate=%s",
            wandb_config.project,
            name,
            group or "-",
            parallel,
            rate,
        )

    def log_metrics(
        self,
        metrics: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> None:
        """Log running aggregates; ``step`` is the request index (0 .. number-1)."""
        if not self._active:
            return
        parallel = int(metrics["parallel"])
        rate = float(metrics["rate"])
        for step in range(len(results)):
            wandb.log(
                running_to_wandb_message(
                    results[: step + 1], parallel=parallel, rate=rate
                ),
                step=step,
            )

    def finish(self) -> None:
        if self._active:
            wandb.finish()
            self._active = False
