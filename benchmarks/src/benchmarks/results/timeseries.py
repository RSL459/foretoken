# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Build completion-window and send-order series from measured requests."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from benchmarks.results.metrics import (
    RequestMeasurement,
    percentile_summary,
    request_activity_events,
)

ELAPSED_TIME = "Elapsed time (s)"
REQUEST_INDEX = "Request index (send order)"


def request_series(
    measurements: list[RequestMeasurement],
    *,
    stream: bool,
    slo_met: list[bool] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield each logical request in stable send order, including failures."""
    ordered = sorted(
        enumerate(measurements), key=lambda item: item[1].started_at
    )
    for index, (measurement_index, item) in enumerate(ordered, 1):
        row = {
            REQUEST_INDEX: index,
            "Requests/E2EL (s)": item.latency,
            "Requests/Success": int(item.succeeded),
        }
        if slo_met is not None:
            row["Requests/SLO met"] = int(slo_met[measurement_index])
        if item.input_tokens is not None:
            row["Requests/Input tokens"] = item.input_tokens
        if item.target_output_tokens is not None:
            row["Requests/Target output tokens"] = item.target_output_tokens
        if item.output_tokens is not None:
            row["Requests/Output tokens"] = item.output_tokens
        if item.cached_input_tokens is not None:
            row["Requests/Cached input tokens"] = item.cached_input_tokens
        if stream and item.succeeded:
            if item.ttft is not None:
                row["Requests/TTFT (s)"] = item.ttft
            if item.tpot is not None:
                row["Requests/TPOT (ms)"] = item.tpot * 1000
        yield row


class CumulativeMetrics:
    """Accumulate completed request metrics for live and saved-result consumers."""

    def __init__(self, *, stream: bool) -> None:
        self.stream = stream
        self.completed = self.succeeded = 0
        self.input_tokens: int | None = 0
        self.output_tokens: int | None = 0
        self.latency = self.ttft = self.tpot = self.itl = 0.0
        self.ttft_count = self.tpot_count = self.itl_count = 0

    def observe(self, item: RequestMeasurement) -> None:
        """Add one completed logical HTTP request, including failures in request counts."""
        self.completed += 1
        if not item.succeeded:
            return
        self.succeeded += 1
        self.input_tokens = (
            self.input_tokens + item.input_tokens
            if self.input_tokens is not None and item.input_tokens is not None else None
        )
        self.output_tokens = (
            self.output_tokens + item.output_tokens
            if self.output_tokens is not None and item.output_tokens is not None else None
        )
        self.latency += item.latency
        if self.stream:
            if item.ttft is not None:
                self.ttft += item.ttft
                self.ttft_count += 1
            if item.tpot is not None:
                self.tpot += item.tpot
                self.tpot_count += 1
            if item.itl_summary["count"]:
                self.itl += item.itl_summary["mean"] * item.itl_summary["count"]
                self.itl_count += item.itl_summary["count"]

    def row(self, elapsed: float) -> dict[str, Any]:
        """Publish counts, running mean latencies, and throughput since measurement start."""
        row: dict[str, Any] = {
            ELAPSED_TIME: elapsed,
            "Cumulative/Completed requests": self.completed,
            "Cumulative/Successful requests": self.succeeded,
            "Cumulative/Failed requests": self.completed - self.succeeded,
        }
        if self.completed:
            row["Cumulative/Success rate (%)"] = 100 * self.succeeded / self.completed
        if self.succeeded:
            row["Cumulative/Mean E2EL (s)"] = self.latency / self.succeeded
            if self.input_tokens is not None:
                row["Cumulative/Mean input tokens"] = self.input_tokens / self.succeeded
            if self.output_tokens is not None:
                row["Cumulative/Mean output tokens"] = self.output_tokens / self.succeeded
        if elapsed > 0:
            row["Cumulative/Request throughput (req/s)"] = self.succeeded / elapsed
            if self.input_tokens is not None:
                row["Cumulative/Input token throughput (tokens/s)"] = self.input_tokens / elapsed
            if self.output_tokens is not None:
                row["Cumulative/Output token throughput (tokens/s)"] = self.output_tokens / elapsed
            if self.input_tokens is not None and self.output_tokens is not None:
                row["Cumulative/Total token throughput (tokens/s)"] = (self.input_tokens + self.output_tokens) / elapsed
        if self.ttft_count:
            row["Cumulative/Mean TTFT (s)"] = self.ttft / self.ttft_count
        if self.tpot_count:
            row["Cumulative/Mean TPOT (ms)"] = 1000 * self.tpot / self.tpot_count
        if self.itl_count:
            row["Cumulative/Mean ITL (ms)"] = 1000 * self.itl / self.itl_count
        return row


def cumulative_series(
    measurements: list[RequestMeasurement], *, stream: bool
) -> Iterator[dict[str, Any]]:
    """Yield running aggregates in completion order on the elapsed-time axis."""
    metrics = CumulativeMetrics(stream=stream)
    for item in sorted(measurements, key=lambda item: item.started_at + item.latency):
        metrics.observe(item)
        yield metrics.row(item.started_at + item.latency)


def time_series(
    measurements: list[RequestMeasurement], *, duration: float, stream: bool,
    slo_met: list[bool] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield one-second completion windows and time-weighted in-flight request counts.

    Token throughput attributes a request's tokens to its completion window,
    not to individual streamed token arrivals. SLO values use the caller's
    per-request decisions on the original measurement indexes. Empty completion
    windows report zero counts and throughput but no fraction or latency sample.
    """
    if not measurements:
        return
    end = max(duration, max(item.started_at + item.latency for item in measurements))
    if end <= 0:
        return
    count = math.ceil(end)
    completed: dict[int, list[tuple[int, RequestMeasurement]]] = defaultdict(list)
    arrivals: dict[int, int] = defaultdict(int)
    events = request_activity_events(measurements)
    for measurement_index, item in enumerate(measurements):
        stop = item.started_at + item.latency
        completed[min(int(stop), count - 1)].append((measurement_index, item))
        arrivals[min(int(item.started_at), count - 1)] += 1
    # Integrate concurrency between request starts and finishes, carrying active
    # requests across window boundaries rather than sampling only at each edge.
    event_index = active = 0
    position = 0.0
    for index in range(count):
        left, right = float(index), min(float(index + 1), end)
        width = right - left
        area = 0.0
        while event_index < len(events) and events[event_index][0] <= right:
            timestamp, change = events[event_index]
            area += active * (timestamp - position)
            position = timestamp
            active += change
            event_index += 1
        area += active * (right - position)
        position = right
        finished = completed[index]
        rows = [item for _, item in finished]
        successful = [item for item in rows if item.succeeded]
        row: dict[str, Any] = {
            ELAPSED_TIME: right,
            "Time/Window duration (s)": width,
            "Time/Started requests per second": arrivals[index] / width,
            "Time/Completed requests in window": len(rows),
            "Time/Successful requests in window": len(successful),
            "Time/Failed requests in window": len(rows) - len(successful),
            "Time/Request throughput (req/s)": len(successful) / width,
            "Time/Mean in-flight requests": area / width,
        }
        if all(item.input_tokens is not None for item in successful):
            row["Time/Completed input tokens per second"] = (
                sum(int(item.input_tokens) for item in successful) / width
            )
        if all(item.output_tokens is not None for item in successful):
            row["Time/Completed output tokens per second"] = (
                sum(int(item.output_tokens) for item in successful) / width
            )
        if rows:
            row["Time/Failure rate (%)"] = 100 * (len(rows) - len(successful)) / len(rows)
        if slo_met is not None:
            passing = [item for measurement_index, item in finished if slo_met[measurement_index]]
            if rows:
                row["Time/SLO attainment (%)"] = 100 * len(passing) / len(rows)
            row["Time/SLO request goodput (req/s)"] = len(passing) / width
            if all(item.output_tokens is not None for item in passing):
                row["Time/SLO token goodput (tokens/s)"] = sum(
                    int(item.output_tokens) for item in passing
                ) / width
        if successful:
            row["Time/E2EL p95 (s)"] = percentile_summary(
                [item.latency for item in successful]
            )["p95"]
            if stream:
                timing_fields = (
                    ("ttft", "TTFT", 1.0, "s"),
                    ("tpot", "TPOT", 1000.0, "ms"),
                )
                for field, label, scale, unit in timing_fields:
                    values = [
                        getattr(item, field) * scale
                        for item in successful
                        if getattr(item, field) is not None
                    ]
                    if values:
                        row[f"Time/{label} p95 ({unit})"] = percentile_summary(values)["p95"]
        yield row
