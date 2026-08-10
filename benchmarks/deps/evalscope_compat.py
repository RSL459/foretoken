# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Thin bridge onto EvalScope perf APIs.

Maps Foretoken ``BenchConfig`` to ``evalscope.perf.arguments.Arguments`` for
workload generation, without re-implementing EvalScope argument construction.
"""

from __future__ import annotations

from typing import Any, Optional

from evalscope.perf.arguments import Arguments
from evalscope.perf.plugin.datasets.random_dataset import RandomDatasetPlugin

from benchmarks.config import BenchConfig


def import_random_dataset_plugin() -> type:
    """Return EvalScope ``RandomDatasetPlugin``."""
    return RandomDatasetPlugin


def build_perf_arguments(
    config: BenchConfig,
    *,
    number: Optional[int] = None,
    dataset: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> Any:
    """Build EvalScope ``Arguments`` from ``BenchConfig``.

    Fields are filled from the Foretoken config, then constructed with
    ``Arguments.model_construct``.
    """
    ds = config.dataset
    apply_chat = ds.resolve_apply_chat_template(config.target.url)
    kwargs: dict[str, Any] = {
        "model": config.target.model,
        "url": config.target.url,
        "api_key": config.target.api_key or None,
        "dataset": (
            dataset
            if dataset is not None
            else (ds.dataset[0] if ds.dataset else None)
        ),
        "tokenizer_path": ds.tokenizer_path or None,
        "number": config.load.number[0] if number is None else number,
        "parallel": config.load.parallel[0],
        "rate": float(config.load.rate[0]),
        "open_loop": config.load.open_loop,
        "min_prompt_length": ds.min_prompt_length,
        "max_prompt_length": ds.max_prompt_length,
        "prefix_length": ds.prefix_length,
        "dataset_offset": ds.dataset_offset,
        "apply_chat_template": apply_chat,
        "tokenize_prompt": False,
        "dataset_args": {},
        "num_workers": 0,
        "warmup_num": 0,
        "max_tokens": config.generation.max_tokens,
        "temperature": config.generation.temperature,
        "stream": config.generation.stream,
        "sla_auto_tune": config.output.sla_auto_tune,
    }
    if extra:
        kwargs.update(extra)
    return Arguments.model_construct(**kwargs)
