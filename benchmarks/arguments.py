# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""CLI commands and benchmark argument mapping."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import MISSING, dataclass, fields
from typing import Any

from evalscope.perf.arguments import Arguments

from benchmarks.config import (
    BenchConfig,
    DatasetConfig,
    GenerationConfig,
    LoadConfig,
    OutputConfig,
    ParamSweepConfig,
    EndpointConfig,
    WandbConfig,
)


@dataclass(frozen=True)
class BenchCommand:
    """Run a benchmark against a deployment or existing endpoint."""

    deploy: str
    config: BenchConfig
    wait_timeout: str


def _default(cls: type, name: str) -> Any:
    field_info = next(item for item in fields(cls) if item.name == name)
    if field_info.default_factory is not MISSING:
        return field_info.default_factory()
    if field_info.default is not MISSING:
        return field_info.default
    raise KeyError(name)


def _output_destinations(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _add_benchmark_arguments(parser: argparse.ArgumentParser) -> None:
    # Service source
    service_source = parser.add_mutually_exclusive_group(required=True)
    service_source.add_argument(
        "--deploy",
        default="",
        help="Kustomize directory to deploy or reuse for this benchmark",
    )
    service_source.add_argument(
        "--url",
        default="",
        help="Existing OpenAI-compatible API URL",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Model name; inferred when the deployment contains one model",
    )
    parser.add_argument(
        "--api-key", default=_default(EndpointConfig, "api_key"), help="API key"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=_default(EndpointConfig, "timeout"),
        help="Request timeout seconds",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=_default(EndpointConfig, "max_retries"),
        help="OpenAI client max retries on transient failures",
    )
    parser.add_argument(
        "--wait-timeout",
        default="15m",
        help="Timeout for each deployment readiness stage",
    )

    # Load
    parser.add_argument(
        "--parallel",
        type=int,
        default=_default(LoadConfig, "parallel"),
        help="Concurrency (closed-loop). Sweep via --bench-params list values",
    )
    parser.add_argument(
        "--number",
        type=int,
        default=_default(LoadConfig, "number"),
        help=(
            "Request count (total across all --dataset values when multiple). "
            "Sweep via --bench-params list values"
        ),
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=_default(LoadConfig, "rate"),
        help=(
            "Arrival rate (req/s). Must be -1 (no pacing) or > 0 (Poisson). "
            "Still closed-loop unless --open-loop. Sweep via --bench-params"
        ),
    )
    parser.add_argument(
        "--open-loop",
        action="store_true",
        default=_default(LoadConfig, "open_loop"),
        help="Open-loop: no concurrency limit; optionally pace with --rate",
    )

    # Generation
    parser.add_argument(
        "--max-tokens",
        type=int,
        nargs="+",
        default=_default(GenerationConfig, "max_tokens"),
        help=(
            "Max generation tokens: one value (fixed) or two values "
            "MIN MAX for uniform sampling per request"
        ),
    )
    sampling = parser.add_argument_group("sampling parameters")
    sampling.add_argument(
        "--top-p",
        type=float,
        default=_default(GenerationConfig, "top_p"),
        help="Top-p sampling parameter",
    )
    sampling.add_argument(
        "--top-k",
        type=int,
        default=_default(GenerationConfig, "top_k"),
        help="Top-k sampling parameter",
    )
    sampling.add_argument(
        "--min-p",
        type=float,
        default=_default(GenerationConfig, "min_p"),
        help="Min-p sampling parameter",
    )
    sampling.add_argument(
        "--temperature",
        type=float,
        default=_default(GenerationConfig, "temperature"),
        help="Temperature sampling parameter",
    )
    sampling.add_argument(
        "--frequency-penalty",
        type=float,
        default=_default(GenerationConfig, "frequency_penalty"),
        help="Frequency penalty sampling parameter",
    )
    sampling.add_argument(
        "--presence-penalty",
        type=float,
        default=_default(GenerationConfig, "presence_penalty"),
        help="Presence penalty sampling parameter",
    )
    sampling.add_argument(
        "--repetition-penalty",
        type=float,
        default=_default(GenerationConfig, "repetition_penalty"),
        help="Repetition penalty sampling parameter",
    )
    parser.add_argument(
        "--extra-body",
        type=json.loads,
        default=_default(GenerationConfig, "extra_body"),
        help="JSON object of extra body parameters included in each request",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=_default(GenerationConfig, "stream"),
        help=(
            "Stream responses (default). --no-stream sends non-streaming "
            "requests and reports latency only (no TTFT/TPOT)"
        ),
    )

    # Dataset
    parser.add_argument(
        "--dataset",
        type=lambda value: [item.strip() for item in value.split(",") if item.strip()],
        default=_default(DatasetConfig, "dataset"),
        help=(
            "Workload source(s), comma-separated: 'random', local JSONL "
            "path(s), Hugging Face id(s) ('org/name:split'), and/or "
            "HF file URIs ('hf://datasets/org/name[@rev]/path/to.jsonl'). "
            "Multiple sources run sequentially; --number is the total "
            "across all"
        ),
    )
    parser.add_argument(
        "--dataset-offset",
        type=int,
        default=_default(DatasetConfig, "dataset_offset"),
        help="Skip first N samples (JSONL/HF) or token-sequence offset (random)",
    )
    parser.add_argument(
        "--tokenizer-path",
        default=_default(DatasetConfig, "tokenizer_path"),
        help="Tokenizer path (required for --dataset random)",
    )
    parser.add_argument(
        "--min-prompt-length",
        type=int,
        default=_default(DatasetConfig, "min_prompt_length"),
        help="Minimum prompt length in tokens (random: sampled inner length)",
    )
    parser.add_argument(
        "--max-prompt-length",
        type=int,
        default=_default(DatasetConfig, "max_prompt_length"),
        help="Maximum prompt length in tokens (random: sampled inner length)",
    )
    parser.add_argument(
        "--prefix-length",
        type=int,
        default=_default(DatasetConfig, "prefix_length"),
        help="Shared prefix token length (random dataset only)",
    )
    parser.add_argument(
        "--apply-chat-template",
        action=argparse.BooleanOptionalAction,
        default=_default(DatasetConfig, "apply_chat_template"),
        help="Apply chat template (default: auto from URL)",
    )
    parser.add_argument(
        "--prompt",
        default=_default(DatasetConfig, "prompt"),
        help="Fixed prompt text; overrides dataset",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=_default(DatasetConfig, "max_turns"),
        help="Max user turns for custom_multi_turn",
    )

    # Output
    parser.add_argument(
        "--sla-auto-tune",
        action=argparse.BooleanOptionalAction,
        default=_default(OutputConfig, "sla_auto_tune"),
        help="Enable SLA auto-tune search",
    )
    parser.add_argument(
        "--eval-suite",
        default=_default(OutputConfig, "eval_suite"),
        help="Correctness suite: none | general | tool | both",
    )
    parser.add_argument(
        "--output",
        type=_output_destinations,
        default=_default(OutputConfig, "destinations"),
        help="Comma-separated outputs: local, wandb, and quiet",
    )
    parser.add_argument(
        "--output-dir",
        default=_default(OutputConfig, "output_dir"),
        help="Directory for JSON and W&B artifacts",
    )

    # W&B
    parser.add_argument(
        "--wandb-project",
        default=_default(WandbConfig, "project"),
        help="W&B project",
    )
    parser.add_argument(
        "--wandb-entity",
        default=_default(WandbConfig, "entity"),
        help="W&B entity",
    )
    parser.add_argument(
        "--wandb-run-name",
        default=_default(WandbConfig, "run_name"),
        help="W&B name base; default {model}_{YYYYMMDD_HHMMSS}; "
        "runs become {base}_{config}",
    )

    # Param sweep
    parser.add_argument(
        "--bench-params",
        default=_default(ParamSweepConfig, "bench_params"),
        help=(
            "JSONL path of bench parameter combinations that change request "
            "execution (load/generation/dataset/endpoint). "
            "parallel/number/rate may be lists"
        ),
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=_default(ParamSweepConfig, "num_runs"),
        help="Repeats per bench-params combination",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=_default(ParamSweepConfig, "dry_run"),
        help="Print bench-params plan without executing",
    )
    parser.add_argument(
        "--experiment-name",
        default=_default(ParamSweepConfig, "experiment_name"),
        help="Param-sweep experiment subdir under --output-dir",
    )


def _bench_config(namespace: argparse.Namespace) -> BenchConfig:
    return BenchConfig(
        endpoint=EndpointConfig(
            url=namespace.url,
            model=namespace.model,
            api_key=namespace.api_key,
            timeout=namespace.timeout,
            max_retries=namespace.max_retries,
        ),
        load=LoadConfig(
            parallel=namespace.parallel,
            number=namespace.number,
            rate=namespace.rate,
            open_loop=namespace.open_loop,
        ),
        generation=GenerationConfig(
            max_tokens=Arguments._validate_max_tokens(namespace.max_tokens),
            stream=namespace.stream,
            top_p=namespace.top_p,
            top_k=namespace.top_k,
            min_p=namespace.min_p,
            temperature=namespace.temperature,
            frequency_penalty=namespace.frequency_penalty,
            presence_penalty=namespace.presence_penalty,
            repetition_penalty=namespace.repetition_penalty,
            extra_body=namespace.extra_body,
        ),
        dataset=DatasetConfig(
            dataset=namespace.dataset,
            dataset_offset=namespace.dataset_offset,
            tokenizer_path=namespace.tokenizer_path,
            min_prompt_length=namespace.min_prompt_length,
            max_prompt_length=namespace.max_prompt_length,
            prefix_length=namespace.prefix_length,
            apply_chat_template=namespace.apply_chat_template,
            prompt=namespace.prompt,
            max_turns=namespace.max_turns,
        ),
        output=OutputConfig(
            destinations=namespace.output,
            output_dir=namespace.output_dir,
            eval_suite=namespace.eval_suite,
            sla_auto_tune=namespace.sla_auto_tune,
        ),
        wandb=WandbConfig(
            project=namespace.wandb_project,
            entity=namespace.wandb_entity,
            run_name=namespace.wandb_run_name,
        ),
        param_sweep=ParamSweepConfig(
            bench_params=namespace.bench_params,
            num_runs=namespace.num_runs,
            dry_run=namespace.dry_run,
            experiment_name=namespace.experiment_name,
        ),
    )


def parse_arguments(argv: Sequence[str] | None = None) -> BenchCommand:
    """Parse the ``foretoken bench`` command."""
    parser = argparse.ArgumentParser(
        prog="foretoken",
        description="Benchmark Foretoken and OpenAI-compatible inference services",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    bench = subparsers.add_parser(
        "bench",
        help="Benchmark a deployed Foretoken service or an existing endpoint",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _add_benchmark_arguments(bench)

    namespace = parser.parse_args(argv)
    if namespace.url and not namespace.model:
        bench.error("--model is required with --url")
    return BenchCommand(
        deploy=namespace.deploy,
        config=_bench_config(namespace),
        wait_timeout=namespace.wait_timeout,
    )
