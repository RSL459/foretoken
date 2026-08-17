# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Typed benchmark configuration: one dataclass per concern."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from evalscope.perf.multi_turn_args import IntOrRange


@dataclass
class EndpointConfig:
    """Inference service URL, model, and request options."""

    url: str
    model: str
    api_key: str = "EMPTY"
    timeout: int = 300
    max_retries: int = 2
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class LoadConfig:
    """Concurrency, request count, arrival rate, and open/closed loop."""

    parallel: int = 1
    number: int = 100
    # -1 = no pacing; >0 = Poisson pacing. Open-loop needs open_loop=True.
    rate: float = -1.0
    open_loop: bool = False

    @staticmethod
    def validate_point(*, parallel: int, rate: float) -> None:
        """Reject load points that would hang or silently drop pacing."""
        if parallel < 1:
            raise ValueError(f"parallel must be >= 1, got {parallel}")
        rate_value = float(rate)
        if rate_value != -1 and rate_value <= 0:
            raise ValueError(
                f"rate must be -1 (no pacing) or > 0, got {rate}"
            )

    def validate(self) -> None:
        """Validate load settings."""
        self.validate_point(parallel=int(self.parallel), rate=float(self.rate))
        if self.number < 1:
            raise ValueError(f"--number must be >= 1, got {self.number}")


@dataclass
class GenerationConfig:
    """Sampling and generation parameters for each request."""

    max_tokens: IntOrRange = 128
    stream: bool = True
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    min_p: Optional[float] = None
    temperature: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    extra_body: dict[str, Any] = field(default_factory=dict)

    def request_overrides(self) -> dict[str, Any]:
        """Return vLLM-compatible request fields with ``extra_body`` applied last."""
        sampling = {
            "top_p": self.top_p,
            "top_k": self.top_k,
            "min_p": self.min_p,
            "temperature": self.temperature,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "repetition_penalty": self.repetition_penalty,
        }
        return {
            **{key: value for key, value in sampling.items() if value is not None},
            **self.extra_body,
        }


def allocate_dataset_counts(total: int, n: int) -> list[int]:
    """Split ``total`` requests across ``n`` datasets as evenly as possible."""
    if n <= 0:
        raise ValueError("dataset count must be > 0")
    if total < 0:
        raise ValueError("total request count must be >= 0")
    base, rem = divmod(total, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


@dataclass
class DatasetConfig:
    """Workload source and prompt shaping.

    ``dataset`` is a list of unified source selectors:
    - ``random``: synthetic prompts (requires ``tokenizer_path``; alone only)
    - local JSONL path: one messages/prompt object per line
    - Hugging Face id: ``org/name:split`` (split required)
    - Hugging Face file URI: ``hf://datasets/{repo}[@{revision}]/{path}``
      (cached via Hub, then read as JSONL)

    Multiple JSONL/HF sources run sequentially; ``LoadConfig.number`` is the
    total request count across all of them.
    """

    dataset: list[str] = field(default_factory=list)
    dataset_offset: int = 0
    tokenizer_path: str = ""
    min_prompt_length: int = 0
    max_prompt_length: int = 131072
    prefix_length: int = 0
    apply_chat_template: Optional[bool] = None
    prompt: str = ""
    max_turns: Optional[int] = None

    def resolve_apply_chat_template(self, url: str) -> bool:
        """Default to chat template when the URL is a chat/completions endpoint."""
        if self.apply_chat_template is not None:
            return self.apply_chat_template
        return url.rstrip("/").endswith("chat/completions")

@dataclass
class OutputConfig:
    """Result destinations, location, and analysis knobs."""

    destinations: tuple[str, ...] = ()
    output_dir: str = "results"
    eval_suite: str = "none"
    sla_auto_tune: bool = False

    def includes(self, destination: str) -> bool:
        return destination in self.destinations

    def validate(self) -> None:
        allowed = {"local", "wandb", "quiet"}
        unknown = set(self.destinations) - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown --output destination: {names}")


@dataclass
class WandbConfig:
    """Weights & Biases connection settings."""

    project: str = "foretoken-bench"
    entity: str = ""
    run_name: str = ""


@dataclass
class ParamSweepConfig:
    """Bench-params JSONL sweep against an already-running service."""

    bench_params: str = ""
    num_runs: int = 1
    dry_run: bool = False
    experiment_name: str = ""


@dataclass
class BenchConfig:
    """Root benchmark configuration (framework contract)."""

    endpoint: EndpointConfig
    load: LoadConfig = field(default_factory=LoadConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    wandb: WandbConfig = field(default_factory=WandbConfig)
    param_sweep: ParamSweepConfig = field(default_factory=ParamSweepConfig)

    def validate(self) -> None:
        """Validate nested configs before a run starts."""
        self.load.validate()
        self.output.validate()
        dataset = self.dataset
        if not dataset.prompt and not dataset.dataset:
            raise ValueError(
                "No workload source. Pass --prompt or --dataset "
                "(random | local JSONL | org/name:split | "
                "hf://datasets/...)."
            )
        if dataset.prompt and len(dataset.dataset) > 1:
            raise ValueError(
                "--prompt cannot be combined with multiple --dataset values"
            )
        if len(dataset.dataset) > 1 and "random" in dataset.dataset:
            raise ValueError(
                "--dataset random cannot be combined with other dataset sources"
            )
        if dataset.dataset == ["random"] and not dataset.tokenizer_path:
            raise ValueError(
                "--tokenizer-path is required when --dataset random"
            )
        if (
            dataset.dataset == ["random"]
            and dataset.max_prompt_length < dataset.min_prompt_length
        ):
            raise ValueError(
                "--max-prompt-length must be >= --min-prompt-length"
            )

    def summary(self) -> str:
        """Human-readable config banner for the console."""
        dataset = self.dataset
        if dataset.prompt:
            dataset_label = "prompt=<fixed>"
        elif dataset.dataset == ["random"]:
            dataset_label = (
                f"random "
                f"(prefix={dataset.prefix_length}, "
                f"min={dataset.min_prompt_length}, "
                f"max={dataset.max_prompt_length})"
            )
        elif len(dataset.dataset) > 1:
            dataset_label = f"{dataset.dataset} (total number across all)"
        else:
            dataset_label = (
                dataset.dataset[0] if dataset.dataset else "<none>"
            )
        open_loop = self.load.open_loop
        if open_loop:
            parallel_label = "unlimited (open-loop)"
        else:
            parallel_label = str(self.load.parallel)

        rate = float(self.load.rate)
        if rate > 0:
            mode = "open-loop" if open_loop else "closed-loop"
            rate_label = f"{rate:g} req/s ({mode}, Poisson pacing)"
        else:
            rate_label = "INF (no pacing)"

        return (
            "\n===== Foretoken Benchmark Configuration ====\n"
            f"  URL        : {self.endpoint.url}\n"
            f"  Model      : {self.endpoint.model}\n"
            f"  Parallel   : {parallel_label}\n"
            f"  Number     : {self.load.number}\n"
            f"  Rate       : {rate_label}\n"
            f"  Open Loop  : {open_loop}\n"
            f"  Stream     : {self.generation.stream}\n"
            f"  Dataset    : {dataset_label}\n"
            "============================================\n"
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the serializable benchmark config without credentials."""
        config = asdict(self)
        config["endpoint"].pop("api_key", None)
        return config
