# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Thin Weights & Biases logger for progressive and final benchmark metrics."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import wandb

from benchmarks.config import BenchConfig, WandbConfig

logger = logging.getLogger(__name__)

# Short benches (e.g. --dataset random) often finish under the W&B default
# ~15s system-stats interval and get no System section; sample every 1s.
_SYSTEM_STATS_INTERVAL_S = 1.0

# Stable W&B chart keys (LLM subset).
_TIME_TAKEN = "Test Duration (s)"
_CONCURRENCY = "Concurrency"
_REQUEST_RATE = "Request Rate (req/s)"
_TOTAL_REQUESTS = "Total Requests"
_SUCCEED_REQUESTS = "Success Requests"
_FAILED_REQUESTS = "Failed Requests"
_REQUEST_THROUGHPUT = "Req Throughput (req/s)"
_AVERAGE_LATENCY = "Avg Latency (s)"
_AVERAGE_INPUT_TOKENS = "Avg Input Tokens"
_OUTPUT_TOKEN_THROUGHPUT = "Output Throughput (tok/s)"
_TOTAL_TOKEN_THROUGHPUT = "Total Throughput (tok/s)"
_AVERAGE_TTFT = "Avg TTFT (ms)"
_AVERAGE_TPOT = "Avg TPOT (ms)"
_AVERAGE_ITL = "Avg ITL (ms)"
_AVERAGE_OUTPUT_TOKENS = "Avg Output Tokens"


@dataclass
class _RunningAverages:
    """O(1) running averages for progressive W&B steps."""

    concurrency: int = 0
    rate: float = -1.0
    start: float = field(default_factory=time.perf_counter)
    n_total: int = 0
    n_success: int = 0
    n_failed: int = 0
    total_latency: float = 0.0
    total_ttft: float = 0.0
    n_ttft: int = 0
    total_tpot: float = 0.0
    n_tpot: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def update(self, result: dict[str, Any]) -> dict[str, Any]:
        self.n_total += 1
        if not result["success"]:
            self.n_failed += 1
            return self.to_message()

        self.n_success += 1
        self.total_latency += float(result["latency"])
        self.total_input_tokens += int(result["input_tokens"])
        self.total_output_tokens += int(result["output_tokens"])
        ttft = result["ttft"]
        if ttft is not None:
            self.total_ttft += float(ttft)
            self.n_ttft += 1
        tpot = result["tpot"]
        if tpot is not None:
            self.total_tpot += float(tpot)
            self.n_tpot += 1
        return self.to_message()

    def to_message(self, ndigits: int = 4) -> dict[str, Any]:
        elapsed = time.perf_counter() - self.start
        message: dict[str, Any] = {
            _TIME_TAKEN: round(elapsed, ndigits),
            _CONCURRENCY: self.concurrency,
            _REQUEST_RATE: self.rate,
            _TOTAL_REQUESTS: self.n_total,
            _SUCCEED_REQUESTS: self.n_success,
            _FAILED_REQUESTS: self.n_failed,
            _REQUEST_THROUGHPUT: round(self.n_total / elapsed, ndigits),
            _OUTPUT_TOKEN_THROUGHPUT: round(
                self.total_output_tokens / elapsed, ndigits
            ),
            _TOTAL_TOKEN_THROUGHPUT: round(
                (self.total_input_tokens + self.total_output_tokens) / elapsed,
                ndigits,
            ),
        }
        if self.n_success:
            n = self.n_success
            message[_AVERAGE_LATENCY] = round(self.total_latency / n, ndigits)
            message[_AVERAGE_INPUT_TOKENS] = round(
                self.total_input_tokens / n, ndigits
            )
            message[_AVERAGE_OUTPUT_TOKENS] = round(
                self.total_output_tokens / n, ndigits
            )
        if self.n_ttft:
            message[_AVERAGE_TTFT] = round(
                self.total_ttft / self.n_ttft * 1000, 2
            )
        if self.n_tpot:
            avg_tpot_ms = round(self.total_tpot / self.n_tpot * 1000, 2)
            message[_AVERAGE_TPOT] = avg_tpot_ms
            message[_AVERAGE_ITL] = avg_tpot_ms
        return message


def metrics_to_wandb_message(metrics: dict[str, Any]) -> dict[str, Any]:
    """Map Foretoken ``metrics.json`` to W&B chart keys."""
    thr = metrics["throughput"]
    lat = metrics["latency"]
    ttft = metrics["ttft"]
    tpot = metrics["tpot"]
    return {
        _TIME_TAKEN: round(float(metrics["benchmark_time"]), 4),
        _CONCURRENCY: int(metrics["parallel"]),
        _REQUEST_RATE: float(metrics["rate"]),
        _TOTAL_REQUESTS: int(metrics["request_num"]),
        _SUCCEED_REQUESTS: int(metrics["success_num"]),
        _FAILED_REQUESTS: int(metrics["failed_num"]),
        _REQUEST_THROUGHPUT: round(float(thr["request/s"]), 4),
        _AVERAGE_LATENCY: round(float(lat["mean"]), 4),
        _AVERAGE_INPUT_TOKENS: round(float(metrics["avg_input_tokens"]), 4),
        _OUTPUT_TOKEN_THROUGHPUT: round(float(thr["token/s"]), 4),
        _TOTAL_TOKEN_THROUGHPUT: round(float(thr["total_token/s"]), 4),
        _AVERAGE_TTFT: round(float(ttft["mean"]) * 1000, 2),
        _AVERAGE_TPOT: round(float(tpot["mean"]) * 1000, 2),
        _AVERAGE_ITL: round(float(metrics["itl"]["mean"]) * 1000, 2),
        _AVERAGE_OUTPUT_TOKENS: round(float(metrics["avg_output_tokens"]), 4),
    }


class WandbLogger:
    """Optional W&B session: init, progressive log, final log, finish."""

    def __init__(self) -> None:
        self._enabled = False
        self._running: Optional[_RunningAverages] = None
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

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
        """Initialize W&B; no-op when ``config.wandb`` is off.

        Default run name is ``{model}_{YYYYMMDD_HHMMSS}``. ``--wandb-run-name``
        replaces that base when set. With ``group`` (multi-dataset experiment),
        runs share the group and the name base is the group id; ``name_suffix``
        then yields ``{group}_{suffix}`` per dataset run.
        """
        wb: WandbConfig = config.wandb
        if not wb.enabled:
            return

        os.environ["WANDB_SILENT"] = "true"
        os.environ["WANDB_DIR"] = output_dir
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = group or wb.run_name or f"{config.target.model}_{stamp}"
        name = f"{base}_{name_suffix}" if name_suffix else base
        init_kwargs: dict[str, Any] = {
            "project": wb.project,
            "name": name,
            "config": config.to_dict(),
            "dir": output_dir,
            "settings": wandb.Settings(
                x_stats_sampling_interval=_SYSTEM_STATS_INTERVAL_S
            ),
        }
        if group:
            init_kwargs["group"] = group
        if wb.entity:
            init_kwargs["entity"] = wb.entity
        wandb.init(**init_kwargs)
        self._enabled = True
        self._running = _RunningAverages(
            concurrency=parallel,
            rate=rate,
        )
        logger.info(
            "W&B logging enabled: project=%s name=%s group=%s",
            wb.project,
            name,
            group or "-",
        )

    def log_result(self, result: dict[str, Any]) -> None:
        """Log one request into the progressive W&B step series."""
        if not self._enabled or self._running is None:
            return
        with self._lock:
            wandb.log(self._running.update(result))

    def log_metrics(self, metrics: dict[str, Any]) -> None:
        """Final summary log using Foretoken aggregated metrics."""
        if not self._enabled:
            return
        with self._lock:
            wandb.log(metrics_to_wandb_message(metrics))

    def finish(self) -> None:
        if not self._enabled:
            return
        with self._lock:
            wandb.finish()
            self._enabled = False
            self._running = None
