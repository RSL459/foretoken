# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Persist completed request measurements before aggregate publication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
