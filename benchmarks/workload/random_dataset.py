# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Generate random synthetic prompt requests for ``--dataset random``."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from evalscope.perf.arguments import Arguments
from evalscope.perf.plugin.datasets.random_dataset import RandomDatasetPlugin
from huggingface_hub import snapshot_download

from benchmarks.config import BenchConfig

logger = logging.getLogger(__name__)

# Hub file patterns kept when resolving a remote ``--tokenizer-path``.
_TOKENIZER_ALLOW_PATTERNS = (
    "tokenizer*",
    "vocab*",
    "merges*",
    "special_tokens_map*",
    "added_tokens*",
    "chat_template*",
    "tokenization*",
    "config.json",
)


def resolve_tokenizer_path(tokenizer_path: str) -> str:
    """Resolve ``tokenizer_path`` to a local directory.

    Existing local paths are returned as-is; HuggingFace repo ids are fetched
    with ``_TOKENIZER_ALLOW_PATTERNS`` only.
    """
    local = Path(tokenizer_path).expanduser()
    if local.exists():
        return str(local.resolve())

    logger.info(
        "Resolving tokenizer from HuggingFace repo %r",
        tokenizer_path,
    )
    return snapshot_download(
        repo_id=tokenizer_path,
        allow_patterns=list(_TOKENIZER_ALLOW_PATTERNS),
    )


def _build_perf_arguments(
    config: BenchConfig,
    *,
    tokenizer_path: str,
    number: int,
    min_prompt_length: int,
    max_prompt_length: int,
) -> Arguments:
    """Map ``BenchConfig`` to EvalScope ``Arguments`` for random generation."""
    dataset = config.dataset
    apply_chat = dataset.resolve_apply_chat_template(config.endpoint.url)
    return Arguments.model_construct(
        model=config.endpoint.model,
        url=config.endpoint.url,
        api_key=config.endpoint.api_key,
        dataset="random",
        tokenizer_path=tokenizer_path,
        number=number,
        parallel=config.load.parallel[0],
        rate=float(config.load.rate[0]),
        open_loop=config.load.open_loop,
        min_prompt_length=min_prompt_length,
        max_prompt_length=max_prompt_length,
        prefix_length=dataset.prefix_length,
        dataset_offset=dataset.dataset_offset,
        apply_chat_template=apply_chat,
        tokenize_prompt=False,
        dataset_args={},
        num_workers=0,
        warmup_num=0,
        max_tokens=config.generation.max_tokens,
        temperature=config.generation.temperature,
        stream=config.generation.stream,
        sla_auto_tune=config.output.sla_auto_tune,
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


def _generate_random_requests(
    config: BenchConfig,
    *,
    tokenizer_path: str,
    number: int,
    min_prompt_length: int,
    max_prompt_length: int,
) -> list[dict[str, Any]]:
    arguments = _build_perf_arguments(
        config,
        tokenizer_path=tokenizer_path,
        number=number,
        min_prompt_length=min_prompt_length,
        max_prompt_length=max_prompt_length,
    )
    plugin = RandomDatasetPlugin(arguments)
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


def generate_random_requests(
    config: BenchConfig,
    *,
    number: int | None = None,
    input_lengths: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Build random requests, optionally matching per-request input lengths."""
    dataset = config.dataset
    if not dataset.tokenizer_path:
        raise ValueError(
            "tokenizer_path is required for random data generation"
        )

    tokenizer_path = resolve_tokenizer_path(dataset.tokenizer_path)
    if input_lengths is None:
        count = config.load.number[0] if number is None else number
        return _generate_random_requests(
            config,
            tokenizer_path=tokenizer_path,
            number=count,
            min_prompt_length=dataset.min_prompt_length,
            max_prompt_length=dataset.max_prompt_length,
        )

    if number is not None and number != len(input_lengths):
        raise ValueError("number must match input_lengths")
    positions: dict[int, list[int]] = defaultdict(list)
    for index, input_length in enumerate(input_lengths):
        positions[input_length].append(index)

    requests: list[dict[str, Any] | None] = [None] * len(input_lengths)
    for input_length, indexes in positions.items():
        generated = _generate_random_requests(
            config,
            tokenizer_path=tokenizer_path,
            number=len(indexes),
            min_prompt_length=input_length,
            max_prompt_length=input_length,
        )
        for index, request in zip(indexes, generated):
            requests[index] = request
    if any(request is None for request in requests):
        raise RuntimeError("Random dataset generation returned missing requests")
    return [request for request in requests if request is not None]
