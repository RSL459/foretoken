# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Run native lm-evaluation-harness tasks and retain their reports."""

from __future__ import annotations

import json
import logging
import os
from contextlib import nullcontext
from functools import partial
from pathlib import Path
from typing import Any

from lm_eval import simple_evaluate
from lm_eval.config.evaluate_config import EvaluatorConfig
from lm_eval.loggers import EvaluationTracker, TrackioLogger
from lm_eval.utils import (
    handle_non_serializable,
    setup_logging,
    simple_parse_args_string,
)

from benchmarks.config.evaluation import native_arguments, validate_model_transport
from benchmarks.integrations.lm_eval.model import ServiceEvaluation
from benchmarks.integrations.lm_eval.responses import LmEvalResponses
from benchmarks.results.evaluation import (
    generation_conditions,
    save_evaluation_conditions,
)

logger = logging.getLogger(__name__)


def run_lm_eval(
    arguments: list[str], service: dict[str, Any], directory: str, *, resume: bool = False
) -> None:
    """Resolve native configuration and own the response store for one model-service evaluation."""
    setup_logging()
    args = native_arguments("lm-eval", arguments)
    args.output_path = directory
    if args.config:
        configured = EvaluatorConfig.load_yaml_config(args.config).get("model_args") or {}
        validate_model_transport(
            simple_parse_args_string(configured) if isinstance(configured, str) else configured
        )
    validate_model_transport(args.model_args or {})
    config = EvaluatorConfig.from_cli(args)
    if config.wandb_args:
        raise ValueError("Use --output wandb and --wandb-project instead of native wandb_args")
    if resume and (args.use_cache is not None or config.use_cache is not None):
        raise ValueError("Use --resume or native --use_cache, not both")
    chat_url = service["chat_url"]
    if chat_url.rstrip("/").endswith("/completions"):
        chat_url = f"{service['api_root']}/chat/completions"
    config.model_args.update(model=service["model"], base_url=chat_url)
    config.output_path = directory

    # Keep native tokenizer choices for likelihoods; chat requests remain message lists.
    chat_options = {**config.model_args, "tokenizer_backend": None, "tokenized_requests": False}
    chat_options.pop("tokenizer", None)
    progress = LmEvalResponses(Path(directory).parent) if config.use_cache is None else nullcontext(None)
    with progress as responses:
        model = ServiceEvaluation.create_from_arg_obj(chat_options, {
            "batch_size": config.batch_size, "config": config, "service": service,
            "responses": responses, "resume": resume,
        })
        manager = config.process_tasks(config.metadata)
        manager.load = partial(model.load_tasks, manager.load)
        _execute(config, model, manager)


def _execute(config, model, manager) -> None:
    """Invoke the public evaluator once and save native scores, samples and optional publications."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    config.hf_hub_log_args["output_path"] = config.output_path
    if os.environ.get("HF_TOKEN"):
        config.hf_hub_log_args["token"] = os.environ["HF_TOKEN"]
    tracker = EvaluationTracker(**config.hf_hub_log_args)
    trackio = TrackioLogger(config.trackio_args) if config.trackio_args else None
    try:
        results = simple_evaluate(
            model=model, model_args=config.model_args, tasks=config.tasks,
            num_fewshot=config.num_fewshot, batch_size=config.batch_size,
            max_batch_size=config.max_batch_size, device=config.device,
            use_cache=config.use_cache,
            cache_requests=config.cache_requests.get("cache_requests", False),
            rewrite_requests_cache=config.cache_requests.get("rewrite_requests_cache", False),
            delete_requests_cache=config.cache_requests.get("delete_requests_cache", False),
            limit=config.limit, samples=config.samples, check_integrity=config.check_integrity,
            write_out=config.write_out, log_samples=config.log_samples,
            evaluation_tracker=tracker, system_instruction=config.system_instruction,
            apply_chat_template=config.apply_chat_template,
            fewshot_as_multiturn=config.fewshot_as_multiturn,
            gen_kwargs=config.gen_kwargs, task_manager=manager, verbosity=config.verbosity,
            predict_only=config.predict_only,
            random_seed=config.seed[0] if config.seed else None,
            numpy_random_seed=config.seed[1] if config.seed else None,
            torch_random_seed=config.seed[2] if config.seed else None,
            fewshot_random_seed=config.seed[3] if config.seed else None,
            confirm_run_unsafe_code=config.confirm_run_unsafe_code, metadata=config.metadata,
        )
        if results is None:
            return
        # Native task reports contain the final few-shot and generation overrides,
        # including choices made while constructing this run's requests.
        conditions = {
            "limit": config.limit, "samples": config.samples, "seed": config.seed,
            "system_instruction": config.system_instruction,
            "apply_chat_template": config.apply_chat_template,
            "fewshot_as_multiturn": config.fewshot_as_multiturn,
            "model_options": {key: config.model_args[key] for key in (
                "tokenizer", "tokenizer_backend", "revision", "max_length", "max_gen_toks",
                "seed", "truncate", "eos_string",
            ) if key in config.model_args},
            "tasks": {},
            "unknown": [name for name, unresolved in (
                ("custom_tasks", bool(config.include_path) or any(
                    isinstance(task, dict) or str(task).endswith((".yaml", ".yml")) for task in config.tasks
                )),
                ("seed", config.seed is None or any(seed is None for seed in config.seed)),
                ("samples", isinstance(config.samples, str)),
            ) if unresolved],
        }
        for name, task in results["configs"].items():
            formatting = (task.get("metadata") or {}).get("foretoken") or {}
            native_generation = task.get("generation_kwargs") or {}
            generation = generation_conditions(native_generation)
            conditions["tasks"][name] = {
                **{key: task[key] for key in (
                    "dataset_path", "dataset_name", "test_split", "validation_split",
                    "fewshot_split", "output_type", "repeats",
                ) if key in task},
                "num_fewshot": results["n-shot"][name],
                "generation": {"max_gen_toks": model._max_gen_toks, **generation},
                "formatting": {key: formatting[key] for key in (
                    "prompt_format", "fewshot_as_multiturn", "chat_template",
                ) if key in formatting},
                "version": results.get("versions", {}).get(name),
            }
            if native_generation.keys() - generation.keys():
                conditions["unknown"].append(f"tasks.{name}.generation")
            if "prompt_format" not in formatting:
                conditions["unknown"].append(f"tasks.{name}.formatting")
            if conditions["tasks"][name]["version"] is None:
                conditions["unknown"].append(f"tasks.{name}.version")
        save_evaluation_conditions(config.output_path, conditions)
        samples = results.pop("samples") if config.log_samples else None
        if config.show_config:
            print(json.dumps(results, indent=2, default=handle_non_serializable, ensure_ascii=False))
        tracker.save_results_aggregated(results=results, samples=samples)
        if config.log_samples:
            for task_name in results["configs"]:
                tracker.save_results_samples(task_name=task_name, samples=samples[task_name])
        if tracker.push_results_to_hub or tracker.push_samples_to_hub:
            tracker.recreate_metadata_card()
        if trackio is not None:
            # Optional tracking failures do not discard saved native reports.
            try:
                trackio.post_init(results)
                trackio.log_eval_result()
                if config.log_samples:
                    trackio.log_eval_samples(samples)
            except Exception:
                logger.warning("Logging to Trackio failed", exc_info=True)
    finally:
        if trackio is not None:
            trackio.finish()
