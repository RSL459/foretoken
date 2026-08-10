# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Aggregate per-request results into summary metrics."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np


def _percentile_stats(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
    }


def compute_tpot(
    latency: float,
    ttft: Optional[float],
    output_tokens: int,
) -> Optional[float]:
    if ttft is None:
        return None
    denom = int(output_tokens) - 1
    if denom <= 0:
        return None
    return (latency - ttft) / denom


def user_count_for_throughput(parallel: int) -> int:
    """Denominator for per-user throughput (open-loop parallel < 0 → 1)."""
    return 1 if parallel < 0 else int(parallel)


def tokens_per_s_per_user(token_s: float, parallel: int) -> float:
    return float(token_s) / float(user_count_for_throughput(parallel))


def attach_user_throughput(
    metrics: dict[str, Any],
    *,
    parallel: int,
) -> dict[str, Any]:
    metrics["parallel"] = int(parallel)
    throughput = metrics["throughput"]
    token_s = float(throughput["token/s"])
    throughput["token/s/user"] = tokens_per_s_per_user(token_s, parallel)
    return metrics


def merge_raw_outputs(raws: list[dict[str, Any]]) -> dict[str, Any]:
    """Concatenate per-dataset raw outputs; ``total_time`` is the sum of walls."""
    if not raws:
        raise ValueError("merge_raw_outputs requires at least one raw output")
    results: list[Any] = []
    total_time = 0.0
    for raw in raws:
        results.extend(raw["results"])
        total_time += float(raw["total_time"])
    return {"results": results, "total_time": total_time}


class MetricsAggregator:
    def aggregate(self, output: dict[str, Any]) -> dict[str, Any]:
        results = output["results"]
        success_results = [r for r in results if r["success"]]

        latencies = [float(r["latency"]) for r in success_results]
        ttfts = [
            float(r["ttft"])
            for r in success_results
            if r["ttft"] is not None
        ]
        tpots = [
            float(r["tpot"])
            for r in success_results
            if r["tpot"] is not None
        ]

        output_tokens = sum(int(r["output_tokens"]) for r in success_results)
        input_tokens = sum(int(r["input_tokens"]) for r in success_results)
        total_time = float(output["total_time"])
        success_num = len(success_results)
        failed_num = len(results) - success_num

        return {
            "request_num": len(results),
            "success_num": success_num,
            "failed_num": failed_num,
            "success_rate": success_num / len(results),
            "latency": _percentile_stats(latencies),
            "ttft": _percentile_stats(ttfts),
            "tpot": _percentile_stats(tpots),
            "itl": _percentile_stats(tpots),
            "throughput": {
                "request/s": len(results) / total_time,
                "token/s": output_tokens / total_time,
                "input_token/s": input_tokens / total_time,
                "total_token/s": (input_tokens + output_tokens) / total_time,
            },
            "avg_input_tokens": input_tokens / success_num,
            "avg_output_tokens": output_tokens / success_num,
            "benchmark_time": total_time,
        }
