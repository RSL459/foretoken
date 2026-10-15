# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Persist completed request measurements before aggregate publication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmarks.results.itl import ITLStatistics, ITLSummary
from benchmarks.results.metrics import RequestMeasurement


def _saved_itl_summary(row: dict[str, Any]) -> ITLSummary:
    """Read scalar ITL records, reducing legacy interval arrays at the file boundary."""
    if "itl_summary" in row:
        return row["itl_summary"]
    statistics = ITLStatistics()
    for interval in row.get("inter_token_latencies") or ():
        statistics.observe(interval)
    return statistics.summary()


def load_http_measurements(raw: list[dict[str, Any]]) -> list[RequestMeasurement]:
    """Restore saved HTTP requests for plotting and remote publication."""
    return [
        RequestMeasurement(
            started_at=float(row["start_time"]),
            ttft=row.get("ttft"),
            latency=float(row["latency"]),
            tpot=row.get("tpot"),
            itl_summary=_saved_itl_summary(row),
            input_tokens=row.get("input_tokens"),
            output_tokens=row.get("output_tokens"),
            cached_input_tokens=row.get("cached_input_tokens"),
            succeeded=bool(row["success"]),
            conversation_id=row.get("conversation_id"),
            turn=row.get("turn"),
            status_code=row.get("status_code"),
            error_message=row.get("error"),
            dataset=row.get("dataset"),
            model=row.get("model"),
            priority=row.get("priority"),
            request_class=row.get("request_class"),
            target_output_tokens=row.get("target_output_tokens"),
            request_id=row.get("request_id"),
            phase=row.get("phase"),
            source_id=row.get("source_id"),
            finish_reason=row.get("finish_reason"),
            response_id=row.get("response_id"),
            response_model=row.get("response_model"),
            content_characters=row.get("content_characters"),
            reasoning_characters=row.get("reasoning_characters"),
            transport_completed=row.get("transport_completed"),
            scheduled_at=row.get("scheduled_at"),
            send_delay=row.get("send_delay"),
        )
        for row in raw
    ]


class RequestRecordWriter:
    """Own a flushed JSONL journal so completed requests survive an interrupted run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.file = path.open("w", encoding="utf-8", buffering=1)

    def write(self, record: dict[str, Any]) -> None:
        """Append a completed request without retaining request or response content."""
        self.file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.file.flush()

    def close(self) -> None:
        """Close the journal after the owning result lifecycle finishes publication."""
        self.file.close()
