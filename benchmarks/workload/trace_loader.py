# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Load supported conversation traces as timestamped replay requests."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_HF_TRACE_PREFIX = "hf://"


def _download_hf_trace(repo_id: str, filename: str) -> str:
    """Download one dataset file through the Hugging Face cache."""
    from huggingface_hub import hf_hub_download

    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type="dataset",
    )


@dataclass(frozen=True)
class TraceRequest:
    """One normalized trace event with an optional bound payload."""

    timestamp_s: float
    source_index: int
    messages: list[dict[str, Any]] | None = None
    prompt: str | None = None
    tools: list[dict[str, Any]] | None = None
    input_length: int | None = None
    hash_ids: list[int] | None = None
    conversation_id: str | None = None
    payload_source: str = "trace-native"


class StudyChatAdapter:
    """Convert StudyChat JSONL rows into ``TraceRequest`` objects."""

    @staticmethod
    def parse(
        payload: object,
        *,
        path: Path,
        line_no: int,
        source_index: int,
    ) -> TraceRequest:
        if not isinstance(payload, dict):
            raise ValueError(f"Expected an object at {path}:{line_no}")

        required = ("timestamp", "chatId", "messages")
        missing = [name for name in required if name not in payload]
        if missing:
            raise ValueError(
                f"Missing {', '.join(missing)} at {path}:{line_no}"
            )

        try:
            timestamp_ms = float(payload["timestamp"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid timestamp at {path}:{line_no}") from error
        if not math.isfinite(timestamp_ms):
            raise ValueError(f"Timestamp must be finite at {path}:{line_no}")

        chat_id = payload["chatId"]
        if chat_id is None or not str(chat_id):
            raise ValueError(f"Empty chatId at {path}:{line_no}")

        messages = payload["messages"]
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"Invalid messages at {path}:{line_no}")
        for message_index, message in enumerate(messages):
            if not isinstance(message, dict):
                raise ValueError(
                    f"Invalid message at {path}:{line_no}:{message_index}"
                )
            if not isinstance(message.get("role"), str) or not isinstance(
                message.get("content"), str
            ):
                raise ValueError(
                    f"Each message needs text role/content at "
                    f"{path}:{line_no}:{message_index}"
                )
        if messages[-1]["role"] != "user":
            raise ValueError(
                f"StudyChat request must end with a user message at "
                f"{path}:{line_no}"
            )

        input_length = payload.get("input_length")
        if input_length is not None:
            try:
                input_length = int(input_length)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid input_length at {path}:{line_no}"
                ) from error
            if input_length <= 0:
                raise ValueError(f"Invalid input_length at {path}:{line_no}")

        return TraceRequest(
            timestamp_s=timestamp_ms / 1000.0,
            source_index=source_index,
            messages=list(messages),
            input_length=input_length,
            conversation_id=str(chat_id),
        )


class MooncakeAdapter:
    """Convert Mooncake JSONL rows into timestamped trace events."""

    @staticmethod
    def parse(
        payload: object,
        *,
        path: Path,
        line_no: int,
        source_index: int,
    ) -> TraceRequest:
        if not isinstance(payload, dict):
            raise ValueError(f"Expected an object at {path}:{line_no}")
        if "timestamp" not in payload or "input_length" not in payload:
            raise ValueError(
                f"Mooncake trace needs timestamp and input_length at "
                f"{path}:{line_no}"
            )
        try:
            timestamp_ms = float(payload["timestamp"])
            input_length = int(payload["input_length"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid timestamp or input_length at {path}:{line_no}"
            ) from error
        if not math.isfinite(timestamp_ms) or input_length <= 0:
            raise ValueError(
                f"Invalid timestamp or input_length at {path}:{line_no}"
            )

        hash_ids = payload.get("hash_ids")
        if hash_ids is not None:
            if not isinstance(hash_ids, list) or any(
                isinstance(hash_id, bool)
                or not isinstance(hash_id, int)
                or hash_id < 0
                for hash_id in hash_ids
            ):
                raise ValueError(f"Invalid hash_ids at {path}:{line_no}")

        conversation_id = payload.get("chatId")
        return TraceRequest(
            timestamp_s=timestamp_ms / 1000.0,
            source_index=source_index,
            input_length=input_length,
            hash_ids=hash_ids,
            conversation_id=(
                str(conversation_id) if conversation_id is not None else None
            ),
        )


class TraceLoader:
    """Load and stably order requests from a supported trace format."""

    _ADAPTERS = {
        "studychat": StudyChatAdapter,
        "mooncake": MooncakeAdapter,
    }

    def __init__(self, path: str | Path, trace_format: str):
        self.trace_path = str(path)
        try:
            self.adapter = self._ADAPTERS[trace_format]
        except KeyError as error:
            supported = ", ".join(self._ADAPTERS)
            raise ValueError(
                f"Unsupported trace format {trace_format!r}; "
                f"expected one of {supported}"
            ) from error

    @classmethod
    def supported_formats(cls) -> tuple[str, ...]:
        return tuple(cls._ADAPTERS)

    def _resolve_path(self) -> Path:
        """Return a local trace path, downloading an HF trace if necessary."""
        if not self.trace_path.startswith(_HF_TRACE_PREFIX):
            return Path(self.trace_path).expanduser()

        reference = self.trace_path.removeprefix(_HF_TRACE_PREFIX)
        parts = reference.split("/", maxsplit=2)
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                "HF trace must use hf://org/dataset/path/to/trace.jsonl"
            )
        repo_id = "/".join(parts[:2])
        filename = parts[2]
        logger.info("Resolving Hugging Face trace %s", self.trace_path)
        return Path(_download_hf_trace(repo_id, filename))

    def load_window(
        self,
        *,
        start: float = 0.0,
        duration: float | None = None,
    ) -> tuple[float, list[TraceRequest]]:
        path = self._resolve_path()
        if not path.is_file():
            raise FileNotFoundError(f"Trace JSONL not found: {path}")

        requests: list[TraceRequest] = []
        source_index = 0
        with path.open("r", encoding="utf-8") as file:
            for line_no, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    payload: Any = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSON at {path}:{line_no}: {error}"
                    ) from error
                requests.append(
                    self.adapter.parse(
                        payload,
                        path=path,
                        line_no=line_no,
                        source_index=source_index,
                    )
                )
                source_index += 1

        requests.sort(key=lambda request: request.timestamp_s)
        if not requests:
            raise ValueError("Trace contains no requests")

        first_timestamp = requests[0].timestamp_s
        window_start = first_timestamp + start
        window_end = (
            None if duration is None else window_start + duration
        )
        selected = [
            request
            for request in requests
            if request.timestamp_s >= window_start
            and (window_end is None or request.timestamp_s < window_end)
        ]
        if not selected:
            raise ValueError("Trace window contains no requests")
        return window_start, selected
