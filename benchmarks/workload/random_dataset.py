# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Generate random synthetic prompt requests for ``--dataset random``."""

from __future__ import annotations

from typing import Any

from benchmarks.config import BenchConfig
from benchmarks.deps.evalscope_compat import (
    build_perf_arguments,
    import_random_dataset_plugin,
)


def _to_request(message: Any) -> dict[str, Any]:
    """Normalize a generated message into a request dict."""
    if isinstance(message, list):
        if message and isinstance(message[0], int):
            # Raw token-id lists are not supported by the client yet.
            raise ValueError(
                "tokenize_prompt token-id lists are not supported yet"
            )
        return {"messages": message}
    if isinstance(message, str):
        return {"prompt": message}
    raise TypeError(f"Unexpected message type: {type(message)!r}")


def generate_random_requests(config: BenchConfig) -> list[dict[str, Any]]:
    """Build ``number`` random requests from the benchmark config."""
    ds = config.dataset
    if not ds.tokenizer_path:
        raise ValueError(
            "tokenizer_path is required for random data generation"
        )

    RandomDatasetPlugin = import_random_dataset_plugin()
    args = build_perf_arguments(config, dataset="random")
    plugin = RandomDatasetPlugin(args)

    number = config.load.number[0]
    requests: list[dict[str, Any]] = []
    for message in plugin.build_messages():
        requests.append(_to_request(message))
        if len(requests) >= number:
            break

    if len(requests) < number:
        raise RuntimeError(
            f"Random dataset yielded {len(requests)} messages, need {number}"
        )
    return requests
