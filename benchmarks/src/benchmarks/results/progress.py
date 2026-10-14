# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Publish running HTTP aggregates on the measurement clock, excluding warmup."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from benchmarks.results.metrics import RequestMeasurement
from benchmarks.results.timeseries import CumulativeMetrics


class HttpProgress:
    """Accumulate completed requests and emit live metrics without retaining response content.

    The HTTP runner owns the sampling task. Final publication uses the same counters
    after all requests drain, before the W&B run is finalized.
    """

    def __init__(self, publish: Callable[[dict[str, Any]], None], *, stream: bool) -> None:
        self.publish = publish
        self.metrics = CumulativeMetrics(stream=stream)
        self.origin = 0.0

    def start(self, origin: float) -> None:
        """Use the scheduler clock after preparation and warmup complete."""
        self.origin = origin

    def observe(self, item: RequestMeasurement) -> None:
        """Accumulate a completed formal request for the next live sample."""
        self.metrics.observe(item)

    def emit(self, elapsed: float) -> None:
        """Publish a snapshot on the formal measurement clock."""
        self.publish(self.metrics.row(elapsed))

    async def sample(self) -> None:
        """Update the dashboard once per second, including periods with no completions."""
        while True:
            await asyncio.sleep(1)
            if self.origin:
                self.emit(time.perf_counter() - self.origin)
