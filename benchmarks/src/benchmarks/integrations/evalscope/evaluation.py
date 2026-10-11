# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Run native EvalScope quality tasks and restore their prediction and review caches."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from benchmarks.config.evaluation import native_arguments, validate_model_transport
from benchmarks.results.evaluation import (
    generation_conditions,
    save_evaluation_conditions,
)


def restore_progress(source: Path, native: Path) -> None:
    """Copy an earlier run's native task state into a new evaluation, leaving old reports behind."""
    cache = source / "native"
    if not (cache / "configs" / "task_config.yaml").is_file():
        raise ValueError("The previous EvalScope run has no resumable task configuration")
    for name in ("configs", "predictions", "reviews"):
        if (cache / name).is_dir():
            shutil.copytree(cache / name, native / name)


def run_evalscope(
    arguments: list[str], service: dict[str, Any], directory: str, *, resume: bool = False
) -> None:
    """Use EvalScope's native configuration and runner for the selected HTTP service."""
    from evalscope.config import parse_task_config
    from evalscope.run import run_task

    args = native_arguments(
        "evalscope",
        [
            *arguments,
            "--model",
            service["model"],
            "--api-url",
            service["api_root"],
            "--eval-type",
            "openai_api",
            "--work-dir",
            directory,
            "--no-timestamp",
        ],
    )
    config = parse_task_config(args)
    if resume:
        if config.use_cache is not None:
            raise ValueError("Use --resume or native --use-cache, not both")
        config.use_cache = directory
    validate_model_transport(config.model_args)
    config.model = service["model"]
    config.api_url = service["api_root"]
    config.eval_type = "openai_api"
    config.work_dir = directory
    config.no_timestamp = True
    # The evaluation child owns its environment; credentials do not enter native reports.
    os.environ["EVALSCOPE_API_KEY"] = service["api_key"]
    config.api_key = None
    headers = dict(config.model_args.get("default_headers") or {})
    headers.update(service["headers"])
    if headers:
        config.model_args["default_headers"] = headers
    # Reuse the framework's metadata resolver; do not export model, judge or
    # dataset argument dictionaries, which can carry credentials and opaque extras.
    from evalscope.api.registry import get_benchmark

    generation = generation_conditions(config.generation_config)
    conditions = {
        "limit": config.limit, "seed": config.seed, "repeats": config.repeats,
        "dataset_hub": config.dataset_hub, "chat_template": config.chat_template,
        "generation": generation,
        "tasks": {},
        "judge": {
            "strategy": config.judge.strategy,
            "models": [judge.model_id for judge in config.judge.models],
            "repeats": config.judge.repeats, "aggregation": config.judge.aggregation,
        },
        "unknown": [name for name, unresolved in (
            ("generation.max_tokens", not any(key in generation for key in ("max_tokens", "max_new_tokens"))),
            ("seed", config.seed is None),
            ("agent", config.agent_config is not None),
            ("judge.contract", bool(config.judge.models)),
            ("generation.extras", any(getattr(config.generation_config, field) is not None for field in (
                "extra_body", "extra_query", "extra_headers", "response_schema", "logit_bias",
            ))),
        ) if unresolved],
    }
    for name in config.datasets:
        meta = get_benchmark(name, config).benchmark_meta
        conditions["tasks"][name] = {
            "dataset_id": meta.dataset_id, "dataset_revision": meta.dataset_revision,
            "subsets": meta.subset_list, "few_shot_num": meta.few_shot_num,
            "few_shot_random": meta.few_shot_random,
            "train_split": meta.train_split, "eval_split": meta.eval_split,
            "shuffle": meta.shuffle, "shuffle_choices": meta.shuffle_choices,
            "prompt_template": meta.prompt_template, "system_prompt": meta.system_prompt,
            "few_shot_prompt_template": meta.few_shot_prompt_template,
            "query_template": meta.query_template,
            "evaluation_version": meta.evaluation_version,
        }
        if meta.extra_params:
            conditions["unknown"].append(f"tasks.{name}.extra_params")
    save_evaluation_conditions(directory, conditions)
    reports = run_task(config)
    # A resumed run writes into its cache. Export only this invocation's returned reports.
    if Path(config.work_dir).resolve() != Path(directory).resolve():
        for task, report in reports.items():
            if not report:
                continue
            destination = Path(directory) / "reports" / report.model_name
            destination.mkdir(parents=True, exist_ok=True)
            (destination / f"{task}.json").write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            subsets = {
                subset.name
                for metric in report.metrics
                for category in metric.categories
                for subset in category.subsets
            }
            for kind in ("predictions", "reviews"):
                for subset in subsets:
                    relative = Path(kind) / report.model_name / f"{task}_{subset}.jsonl"
                    source = Path(config.work_dir) / relative
                    if source.exists():
                        target = Path(directory) / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
