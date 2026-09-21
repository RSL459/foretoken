# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Search workload capacity under user-provided service-level constraints."""

from __future__ import annotations

import math
import operator
import os
import re
from dataclasses import replace
from typing import Any, Callable

from benchmarks.config.benchmark import BenchmarkConfig
from benchmarks.datasets.multi_dataset import MultiDatasetBenchmark
from benchmarks.model_service import ModelService
from benchmarks.results.console import log_sla_results
from benchmarks.results.output import (
    BenchmarkRun,
    result_directory_path,
    wandb_group_name,
    write_json,
)
from benchmarks.runs.conversation import ConversationBudgetBenchmark
from benchmarks.runs.http import GeneratedLoadBenchmark, run_http_dataset
from benchmarks.runs.trace import TraceReplayBenchmark


_SLA_ALIASES = {
    "latency.mean": "avg_latency",
    "ttft.mean": "avg_ttft",
    "tpot.mean": "avg_tpot",
    "throughput.requests_per_second": "rps",
    "throughput.generation_tokens_per_second": "tps",
}
_CRITERION = re.compile(r"^(<=|>=|==|<|>)\s*(-?(?:\d+(?:\.\d*)?|\.\d+))$")
_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "<": operator.lt,
    ">": operator.gt,
}


def _metric_value(metrics: dict[str, Any], name: str) -> float | None:
    name = _SLA_ALIASES.get(name, name)
    if name in {"avg_latency", "avg_ttft", "avg_tpot", "rps", "tps"}:
        if name == "rps":
            value = metrics["throughput"].get("requests_per_second")
        elif name == "tps":
            value = metrics["throughput"].get("generation_tokens_per_second")
        else:
            value = metrics[name.removeprefix("avg_")]["mean"]
        return float(value) if value is not None else None
    for prefix in ("p50", "p90", "p95", "p99"):
        if name == f"{prefix}_latency":
            value = metrics["latency"].get(prefix)
            return float(value) if value is not None else None
        if name == f"{prefix}_ttft":
            value = metrics["ttft"].get(prefix)
            return float(value) if value is not None else None
        if name == f"{prefix}_tpot":
            value = metrics["tpot"].get(prefix)
            return float(value) if value is not None else None
    raise ValueError(f"unknown SLA metric: {name}")


def _average_metric_values(
    metrics_list: list[dict[str, Any]], criteria: dict[str, str]
) -> dict[str, float]:
    values: dict[str, float] = {}
    for name in criteria:
        samples = [_metric_value(metrics, name) for metrics in metrics_list]
        if any(value is None for value in samples):
            values[name] = float("nan")
        else:
            values[name] = sum(float(value) for value in samples) / len(samples)
    return values


def _average_values_pass(
    values: dict[str, float], criteria: dict[str, str]
) -> bool:
    for name, expression in criteria.items():
        match = _CRITERION.fullmatch(expression)
        if match is None:
            raise ValueError(f"invalid SLA criterion for {name!r}: {expression!r}")
        value = values.get(name, float("nan"))
        if not math.isfinite(value) or not _OPERATORS[match.group(1)](
            value, float(match.group(2))
        ):
            return False
    return True


class SlaAutoTuneBenchmark:
    """Probe a fixed request budget and publish one W&B run per search point."""

    def __init__(
        self,
        benchmark: BenchmarkConfig,
        service: ModelService,
        *,
        label: str = "",
        output_dir: str | None = None,
    ) -> None:
        self.benchmark = benchmark
        self.service = service
        self.label = label
        self.output_dir = output_dir

    def _run_probe(
        self,
        value: int,
        group_index: int,
        run_index: int,
        base_dir: str,
        wandb_group: str,
    ) -> BenchmarkRun:
        label = f"sla-group-{group_index}-parallel-{value}-run-{run_index + 1}"
        probe_dir = os.path.join(
            base_dir,
            f"group-{group_index}",
            f"parallel-{value}",
            f"run-{run_index + 1}",
        )
        if self.benchmark.trace.trace_selector:
            probe_benchmark = replace(
                self.benchmark,
                trace=replace(self.benchmark.trace, max_concurrency=value),
            )
            return TraceReplayBenchmark(
                probe_benchmark,
                self.service,
                label=label,
                output_dir=probe_dir,
                wandb_group=wandb_group,
            ).run()
        if self.benchmark.resolved_workload.has_multiple_datasets:
            probe_benchmark = replace(
                self.benchmark,
                load=replace(self.benchmark.load, max_concurrency=value),
            )
            return MultiDatasetBenchmark(
                probe_benchmark,
                self.service,
                run_http_dataset,
                output_dir=probe_dir,
                wandb_group=wandb_group,
                label=label,
            ).run()
        if self.benchmark.is_multi_turn:
            probe_benchmark = replace(
                self.benchmark,
                load=replace(self.benchmark.load, max_concurrency=value),
            )
            return ConversationBudgetBenchmark(
                probe_benchmark,
                self.service,
                label=label,
                output_dir=probe_dir,
                wandb_group=wandb_group,
            ).run()
        probe_benchmark = replace(
            self.benchmark,
            load=replace(self.benchmark.load, max_concurrency=value),
        )
        return GeneratedLoadBenchmark(
            probe_benchmark,
            self.service,
            label=label,
            output_dir=probe_dir,
            wandb_group=wandb_group,
        ).run()

    def run(self) -> BenchmarkRun:
        """Binary-search each criterion group while keeping the request budget fixed."""
        if not self.benchmark.sla.params:
            raise ValueError("--sla-params is required for SLA auto-tune")
        base_dir = result_directory_path(
            self.benchmark, self.output_dir, "sla-"
        )
        os.makedirs(base_dir, exist_ok=True)
        wandb_group = wandb_group_name(self.benchmark, self.service)
        summaries: list[dict[str, Any]] = []
        winning_run: BenchmarkRun | None = None
        for group_index, criteria in enumerate(self.benchmark.sla.params):
            cache: dict[int, tuple[BenchmarkRun, list[dict[str, Any]]]] = {}

            def probe(value: int) -> tuple[BenchmarkRun, list[dict[str, Any]]]:
                if value not in cache:
                    runs = [
                        self._run_probe(
                            value, group_index, run_index, base_dir, wandb_group
                        )
                        for run_index in range(self.benchmark.sla.num_runs)
                    ]
                    cache[value] = (runs[-1], [run.metrics for run in runs])
                return cache[value]

            low = self.benchmark.sla.lower_bound
            high = self.benchmark.sla.upper_bound
            best = None
            while low <= high:
                value = (low + high) // 2
                run, metrics_list = probe(value)
                average_values = _average_metric_values(metrics_list, criteria)
                passed = (
                    all(item["success_rate"] >= 1.0 for item in metrics_list)
                    and _average_values_pass(average_values, criteria)
                )
                if passed:
                    best = value
                    winning_run = run
                    low = value + 1
                else:
                    high = value - 1
                summaries.append(
                    {
                        "group": group_index,
                        "parallel": value,
                        "request_budget": self.benchmark.load.request_count,
                        "criteria": criteria,
                        "average_values": average_values,
                        "satisfied": passed,
                    }
                )
            if best is None:
                summaries.append(
                    {
                        "group": group_index,
                        "criteria": criteria,
                        "max_satisfied": None,
                    }
                )
            else:
                summaries.append(
                    {
                        "group": group_index,
                        "criteria": criteria,
                        "max_satisfied": best,
                    }
                )
        if winning_run is None:
            raise ValueError("no SLA probe satisfied the configured criteria")
        artifact = write_json(base_dir, "sla_results.json", {"probes": summaries})
        if not self.benchmark.outputs.includes("quiet"):
            log_sla_results({"probes": summaries})
        winning_run.artifacts["sla_results"] = artifact
        return winning_run
