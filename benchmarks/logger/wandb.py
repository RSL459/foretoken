# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Weights & Biases logging for final benchmark results."""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime
from typing import Any, Optional

import wandb

from benchmarks.config import BenchConfig, WandbConfig
from benchmarks.metrics.aggregator import percentile_stats

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

_TRACE_MAX_BUCKETS = 10_000
_TRACE_TIME = "Trace scheduled time (s)"
_TRACE_PERCENTILE_METRICS = (
    ("latency", "Request latency (s)", 1.0),
    ("ttft", "Request TTFT (ms)", 1000.0),
    ("tpot", "TPOT (ms)", 1000.0),
    ("replay_delay", "Replay delay (s)", 1.0),
    ("trace_e2e_ttft", "Trace E2E TTFT (ms)", 1000.0),
    ("trace_e2e_latency", "Trace E2E latency (s)", 1.0),
)
_TRACE_HISTORY_KEYS = {
    "request/s": "Trace/Scheduled requests (req/s)",
    "success/s": "Trace/Successful requests (req/s)",
    **{
        key: f"Trace/{name} p95"
        for key, name, _ in _TRACE_PERCENTILE_METRICS
    },
}


def metrics_to_wandb_message(metrics: dict[str, Any]) -> dict[str, Any]:
    """Map final Foretoken metrics to stable W&B chart keys."""
    throughput = metrics["throughput"]
    message = {
        _TIME_TAKEN: round(float(metrics["benchmark_time"]), 4),
        _CONCURRENCY: int(metrics["parallel"]),
        _REQUEST_RATE: float(metrics["rate"]),
        _TOTAL_REQUESTS: int(metrics["request_num"]),
        _SUCCEED_REQUESTS: int(metrics["success_num"]),
        _FAILED_REQUESTS: int(metrics["failed_num"]),
        _REQUEST_THROUGHPUT: round(float(throughput["request/s"]), 4),
        _OUTPUT_TOKEN_THROUGHPUT: round(float(throughput["token/s"]), 4),
        _TOTAL_TOKEN_THROUGHPUT: round(float(throughput["total_token/s"]), 4),
    }
    optional = (
        ("avg_input_tokens", _AVERAGE_INPUT_TOKENS, 1.0, 4),
        ("avg_output_tokens", _AVERAGE_OUTPUT_TOKENS, 1.0, 4),
        ("latency", _AVERAGE_LATENCY, 1.0, 4),
        ("ttft", _AVERAGE_TTFT, 1000.0, 2),
        ("tpot", _AVERAGE_TPOT, 1000.0, 2),
    )
    for source, destination, scale, digits in optional:
        value = metrics[source]
        if isinstance(value, dict):
            value = value["mean"]
        if value is not None:
            message[destination] = round(float(value) * scale, digits)
    if _AVERAGE_TPOT in message:
        message[_AVERAGE_ITL] = message[_AVERAGE_TPOT]

    for key, name, scale in _TRACE_PERCENTILE_METRICS:
        stats = metrics.get(key)
        if not isinstance(stats, dict):
            continue
        for percentile, value in stats.items():
            if value is not None:
                message[f"{name}/{percentile}"] = round(
                    float(value) * scale, 4
                )
    return message


def _trace_bucket_rows(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build p95 series from scheduled-time request cohorts."""
    if not results:
        return []
    max_offset = max(float(result["trace_offset_s"]) for result in results)
    bucket_seconds = max(
        1.0,
        math.ceil((max_offset + 1.0) / _TRACE_MAX_BUCKETS),
    )
    buckets: dict[int, list[dict[str, Any]]] = {}
    for result in results:
        bucket = math.floor(
            float(result["trace_offset_s"]) / bucket_seconds
        )
        buckets.setdefault(bucket, []).append(result)

    rows: list[dict[str, Any]] = []
    for bucket in range(max(buckets) + 1):
        bucket_results = buckets.get(bucket, [])
        successful = [result for result in bucket_results if result["success"]]
        row: dict[str, Any] = {
            _TRACE_TIME: bucket * bucket_seconds,
            "request/s": len(bucket_results) / bucket_seconds,
            "success/s": len(successful) / bucket_seconds,
        }
        for key, _, scale in _TRACE_PERCENTILE_METRICS:
            values = [
                float(result[key])
                for result in successful
                if result.get(key) is not None
            ]
            value = percentile_stats(values)["p95"]
            if value is not None:
                row[key] = round(float(value) * scale, 4)
        rows.append(row)
    return rows


class WandbLogger:
    """Optional W&B session that publishes one final benchmark summary."""

    def __init__(self) -> None:
        self._active = False
        self._run: Optional[Any] = None

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
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = group or wandb_config.run_name or f"{config.endpoint.model}_{stamp}"
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
        self._run = wandb.init(**init_kwargs)
        self._active = True
        logger.info(
            "W&B logging enabled: project=%s name=%s group=%s concurrency=%s rate=%s",
            wandb_config.project,
            name,
            group or "-",
            parallel,
            rate,
        )

    def log_metrics(self, metrics: dict[str, Any]) -> None:
        """Publish the final aggregated benchmark metrics."""
        if not self._active:
            return
        message = metrics_to_wandb_message(metrics)
        if "replay_delay" in metrics and self._run is not None:
            self._run.summary.update(message)
        else:
            wandb.log(message)

    def log_trace_results(self, results: list[dict[str, Any]]) -> None:
        """Upload scheduled-time trace history after replay."""
        if not self._active or self._run is None:
            return
        rows = _trace_bucket_rows(results)
        try:
            wandb.define_metric(_TRACE_TIME)
            for wandb_key in _TRACE_HISTORY_KEYS.values():
                wandb.define_metric(wandb_key, step_metric=_TRACE_TIME)
            for row in rows:
                message = {_TRACE_TIME: row[_TRACE_TIME]}
                message.update(
                    {
                        wandb_key: row[key]
                        for key, wandb_key in _TRACE_HISTORY_KEYS.items()
                        if key in row
                    }
                )
                self._run.log(message)
        except Exception:
            logger.exception("Failed to upload W&B trace charts")
            return
        logger.info(
            "W&B trace charts uploaded: requests=%d buckets=%d",
            len(results),
            len(rows),
        )

    def finish(self) -> None:
        if self._active:
            wandb.finish()
            self._active = False
            self._run = None
