# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Read saved result directories and their execution plans without running benchmarks."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from benchmarks.results.plots.data import Chart, _method
from benchmarks.results.plots.measurements import (
    _quality_charts,
    _slo_charts,
    comparison_charts,
)


@dataclass
class SavedResults:
    """Run evidence and comparison inputs consumed by the figure exporter."""

    runs: list[dict[str, Any]]
    points: list[dict[str, Any]]
    summary: list[dict[str, Any]]
    native: list[Chart]
    method_filters: dict[Path, tuple[str, ...]]


@dataclass
class _RecordedRun:
    """One planned measurement, including attempts that produced no metrics."""

    directory: Path
    configuration: Path | None
    conditions: dict[str, Any]
    method: str
    metrics: dict[str, Any] | None
    exit_code: int | None
    started: bool


def _conditions(config: dict[str, Any]) -> dict[str, Any]:
    """Separate saved workload choices from deployment and output locations."""
    conditions = {key: value for key, value in config.items() if key not in {
        "service", "services", "service_choices", "output", "wandb", "sweep", "resolved", "url",
    }}
    if "endpoint" in conditions:
        endpoint = conditions.pop("endpoint")
        conditions.pop("name", None)
        conditions["timeout_s"] = endpoint["timeout_s"]
    for section in ("load", "generation", "dataset"):
        fields = conditions.pop(section, {})
        if isinstance(fields, dict):
            conditions.update(fields)
        else:
            conditions[section] = fields
    slo = conditions.pop("slo", None)
    if isinstance(slo, dict):
        conditions["slo_params"] = slo.get("params")
        if slo.get("search"):
            conditions["slo_search"] = slo
    for field in ("timeout", "max_retries"):
        if field in config.get("service", {}):
            conditions[field] = config["service"][field]
    if config.get("mode") in {"evaluation", "evaluation_comparison"}:
        resolved = conditions.pop("evaluation_conditions", None)
        if resolved is None:
            conditions["unknown"] = ["evaluation_conditions"]
        else:
            conditions.update(resolved)
            conditions["unknown"] = [*resolved.get("unknown", ()), *(
                field for field in ("tasks", "limit", "seed") if field not in resolved
            )]
    return conditions


def _flatten(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Name recorded leaf choices so differences identify the changed field, not whole snapshots."""
    fields = {}
    for key, value in values.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and value:
            fields.update(_flatten(value, name))
        else:
            fields[name] = value
    return fields


def _environment_fields(path: Path) -> tuple[dict[str, Any], set[str]]:
    """Select serving declarations and identify unavailable observations for comparison tables."""
    if not path.is_file():
        return {}, set()
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    fields = _flatten({"client": snapshot.get("client")})
    declarations: set[str] = set()
    serving_path = path.parent / "serving_environments.json"
    phases = {phase: snapshot.get(phase) or {} for phase in ("before", "after")}
    if serving_path.is_file():
        compared = json.loads(serving_path.read_text(encoding="utf-8"))
        phases = {"reference": compared.get("reference") or {}}
        phases.update({f"candidate.{row['label']}": row for row in compared.get("candidates", [])})
    for phase, serving in phases.items():
        values = {key: serving.get(key) for key in ("source", "declared_gpu_count")}
        for kind, keys in (
            ("services", ("model", "backend", "engineArgs", "env", "resources", "replicas", "nodes")),
            ("groups", ("role", "artifacts", "runtime", "resources", "parallelism")),
            ("pods", ()),
            ("nodes", ("node_info", "allocatable")),
        ):
            records = []
            for record in serving.get(kind, []):
                selected = record.get("spec", {}) if kind == "services" else record
                values_by_key = {key: selected[key] for key in keys if key in selected}
                if kind == "services" and "modelPools" in selected:
                    values_by_key["modelPoolNames"] = sorted(pool["name"] for pool in selected["modelPools"])
                    values_by_key["modelPools"] = {pool["name"]: {
                        key: pool[key] for key in ("role", "engineArgs", "env", "resources", "replicas", "nodes")
                        if key in pool
                    } for pool in selected["modelPools"]}
                if kind == "groups":
                    values_by_key["role"] = selected.get("role")
                if kind == "pods":
                    values_by_key = {"images": {
                        container["name"]: container.get("imageID")
                        for container in record.get("container_statuses", [])
                    } or None}
                if kind in {"services", "groups"}:
                    engine = selected.get("runtime", selected).get("engineArgs") or {}
                    values_by_key["precision"] = {key: engine.get(key) for key in ("dtype", "quantization")}
                if "runtime" in values_by_key:
                    values_by_key["runtime"] = {key: selected["runtime"][key] for key in (
                        "backend", "engineArgs", "image", "applicationURL",
                    ) if key in selected["runtime"]}
                    if "env" in selected["runtime"]:
                        values_by_key["runtime"]["env"] = {variable["name"]: {
                            key: variable[key] for key in ("value", "valueFrom") if key in variable
                        } for variable in selected["runtime"]["env"]}
                records.append(values_by_key)
            records.sort(key=lambda record: json.dumps(record, sort_keys=True))
            if not records:
                values[kind] = None
            for index, record in enumerate(records, 1):
                prefix = f"{phase}.{kind}.{index}"
                # Explicit nullable declarations are choices; observed nulls are unavailable evidence.
                if kind == "services":
                    declarations.update(_flatten({key: value for key, value in record.items() if key != "precision"}, prefix))
                elif kind == "groups" and "runtime" in record:
                    declarations.update(_flatten({"runtime": record["runtime"]}, prefix))
                values[f"{kind}.{index}"] = record
        fields.update(_flatten(values, phase))
    return fields, {key for key, value in fields.items() if value is None and key not in declarations}


def _comparison_details(runs: list[dict[str, Any]]) -> None:
    """Annotate comparisons with differing recorded values and unavailable evidence only."""
    for section in ("conditions", "environment"):
        values = []
        unavailable = []
        for run in runs:
            if section == "conditions":
                fields = _flatten({key: value for key, value in run.get(section, {}).items() if key != "unknown"})
                missing = set()
            else:
                fields, missing = _environment_fields(Path(run[section])) if run.get(section) else ({}, set())
            values.append(fields)
            unavailable.append(missing)
        keys = sorted({key for record in values for key in record})
        changed = {key for key in keys if len({
            json.dumps(record[key], sort_keys=True) for record, missing in zip(values, unavailable)
            if key in record and key not in missing
        }) > 1}
        for run, record, missing in zip(runs, values, unavailable):
            unknown = [key for key in keys if key not in record or key in missing]
            if section == "conditions":
                unknown.extend(run.get(section, {}).get("unknown", ()))
            elif record.get("client.source.dirty"):
                unknown.append("client.source")
            if not record:
                unknown.append(section)
            run[f"{section}_changes"] = {key: record[key] for key in keys if key in changed and key in record}
            run[f"{section}_unknown"] = sorted(set(unknown))


def _leaf(
    directory: Path, configuration: Path, conditions: dict[str, Any], method: str,
    exit_code: int | None, started: bool,
) -> _RecordedRun:
    """Read one measurement, retaining the parent's plan when execution never reached it."""
    if (directory / "config.json").is_file():
        configuration = directory / "config.json"
        conditions = _conditions(json.loads(configuration.read_text()))
        started = True
    metrics_path = directory / "metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else None
    return _RecordedRun(directory, configuration, conditions, method, metrics, exit_code, started)


def _recorded_runs(directory: Path, context: dict[str, Any]) -> Iterator[_RecordedRun]:
    """Follow the saved sweep/evaluation plan rather than rediscovering nested native reports."""
    configuration = directory / "config.json"
    if not configuration.is_file():
        search_path = directory / "slo_results.json"
        if search_path.is_file():
            # Search summaries have no top-level configuration. Probe records
            # carry the fixed workload; concurrency and criteria belong to the search.
            probe = next(iter(sorted(directory.glob("group-*/max-concurrency-*/run-*/config.json"))), None)
            conditions = _conditions(json.loads(probe.read_text())) if probe is not None else {}
            for field in ("max_concurrency", "slo_params", "slo_search"):
                conditions.pop(field, None)
            search = json.loads(search_path.read_text())
            conditions.update(
                mode="slo_search", concurrency_limit_unit=search["concurrency_limit_unit"],
                slo_params=[group["criteria"] for group in search["groups"]],
            )
            yield _RecordedRun(directory, probe, conditions, "default", None, context.get("exit_code"), True)
        return
    config = json.loads(configuration.read_text())
    if config.get("mode") in {"parameter_sweep", "video_parameter_sweep"}:
        points_path = directory / "sweep_points.json"
        points = json.loads(points_path.read_text()) if points_path.is_file() else []
        observed = {(point["combination"], point["run_number"]): point for point in points}
        for combination in config["combinations"]:
            children = [directory / combination["dir"] / f"run={number}" for number in range(config["num_runs"])]
            bench = {**config["base"], **combination["bench"]}
            method = _method({"bench": bench})
            planned = {**_conditions(config["base"]), **{
                key: value for key, value in combination["bench"].items()
                if key != "service" and not key.startswith("_")
            }}
            # Repetitions share one prepared point configuration. A completed
            # sibling supplies its resolved model and mode for unfinished repeats.
            saved = next((child / "config.json" for child in children if (child / "config.json").is_file()), None)
            if saved is not None:
                planned = _conditions(json.loads(saved.read_text()))
            for number, child in enumerate(children):
                point = observed.get((combination["dir"], number))
                yield _leaf(child, configuration, planned, method,
                            point["exit_code"] if point is not None else None, point is not None)
        return
    metrics_path = directory / "metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else None
    if metrics is not None and "evaluation_comparison" in metrics:
        # The comparison owns method labels and exit states; child reports own
        # native scores and environment snapshots. Never count the aggregate twice.
        for method in metrics["evaluation_comparison"]["methods"]:
            yield _leaf(directory / method["directory"], configuration, _conditions(config),
                        method["label"], method["exit_code"], method["status"] != "not_started")
        return
    yield _RecordedRun(directory, configuration, _conditions(config), _method({"bench": config}),
                       metrics, context.get("exit_code"), True)


def _parent_plan(directory: Path) -> tuple[Path, str] | None:
    """Locate an enclosing result plan without crossing its command boundary."""
    for parent in directory.parents:
        if (parent / "generated/context.json").is_file():
            break
        configuration = parent / "config.json"
        config = json.loads(configuration.read_text()) if configuration.is_file() else {}
        if config.get("mode") in {"parameter_sweep", "video_parameter_sweep"}:
            return parent, "sweep"
        metrics_path = parent / "metrics.json"
        metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else {}
        if "evaluation_comparison" in metrics:
            return parent, "evaluation"
        if (parent / "slo_results.json").is_file():
            return parent, "slo_search"
    return None


def _selected_runs(
    directory: Path, context: dict[str, Any], plans: dict[Path, list[_RecordedRun]],
) -> Iterator[_RecordedRun]:
    """Restore selected children's methods and exit states from their owning plan."""
    parent = _parent_plan(directory)
    if parent is not None:
        owner, kind = parent
        if kind != "slo_search":
            if owner not in plans:
                plans[owner] = list(_recorded_runs(owner, context))
            selected = [run for run in plans[owner] if run.directory.is_relative_to(directory)]
            if not selected:
                raise FileNotFoundError(f"No planned benchmark results in {directory}")
            yield from selected
            return
        # A search outcome is not the exit state of an individual probe.
        context = {}
    yield from _recorded_runs(directory, context)


@dataclass(frozen=True)
class _ResultDirectory:
    """A saved result set and the optional command record that owns its execution."""

    directory: Path
    group: Path
    context: Path | None


def _enclosing_context(directory: Path) -> Path | None:
    """Find a command record when a user selects one of its result directories directly."""
    return next((path for parent in (directory, *directory.parents)
                 if (path := parent / "generated/context.json").is_file()), None)


def _discover(
    directory: Path, visited: set[Path], *, group: Path | None = None,
    context: Path | None = None,
) -> Iterator[_ResultDirectory]:
    """Descend directory containers, stopping at result owners before their native children."""
    directory = directory.resolve()
    group = group.resolve() if group is not None else None
    if directory in visited:
        return
    visited.add(directory)
    command = directory / "generated/context.json"
    if command.is_file():
        found = False
        for child in sorted((directory / "artifacts").glob("*")):
            if child.is_dir():
                for result in _discover(child, visited, group=group or directory, context=command):
                    found = True
                    yield result
        if not found:
            yield _ResultDirectory(directory, group or directory, command)
        return
    if (directory / "config.json").is_file() or (directory / "slo_results.json").is_file():
        yield _ResultDirectory(directory, group or directory, context or _enclosing_context(directory))
        return
    if (directory / "iterations").is_dir():
        for child in sorted((directory / "iterations").iterdir()):
            if child.is_dir():
                yield from _discover(child, visited, group=child)
        return
    if (directory / "runs").is_dir():
        for child in sorted((directory / "runs").iterdir()):
            if child.is_dir():
                yield from _discover(child, visited, group=group or directory)
        return
    parent = _parent_plan(directory)
    if parent is not None and parent[1] != "slo_search":
        # A selected sweep point still owns its planned repetitions, including
        # children that have not created their directories yet.
        yield _ResultDirectory(directory, group or directory, context or _enclosing_context(directory))
        return
    for child in sorted(directory.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            yield from _discover(child, visited, group=group, context=context)


def _directory_labels(paths: list[Path]) -> dict[Path, str]:
    """Use the shortest distinct directory suffix so equal iteration names remain distinguishable."""
    labels = {}
    for path in paths:
        for width in range(1, len(path.parts) + 1):
            suffix = path.parts[-width:]
            if all(other == path or other.parts[-width:] != suffix for other in paths):
                labels[path] = Path(*suffix).as_posix()
                break
    return labels


def read_saved_results(
    sources: tuple[Path, ...], *, methods: tuple[str, ...] = (),
) -> SavedResults:
    """Read directory selections once and group measurements by their recorded workloads.

    Experiment iterations and declared sweep repetitions retain their statistical
    identity. Standalone result sets remain separate approaches. Native scores keep
    evaluator errors, and incomplete command records remain visible without metrics.
    """
    selected = list(dict.fromkeys(path.resolve() for path in sources))
    for path in selected:
        if not path.is_dir():
            raise NotADirectoryError(f"Result directory does not exist: {path}")
    # An enclosing selection owns traversal of its descendants, independently of
    # argument order. This also avoids counting aggregate reports and their children.
    selected = [path for path in selected if not any(
        path != parent and path.is_relative_to(parent) for parent in selected
    )]
    directories: list[_ResultDirectory] = []
    for source in selected:
        discovered = list(_discover(source, set()))
        if not discovered:
            raise FileNotFoundError(f"No saved benchmark results in {source}")
        directories.extend(discovered)
    labels = _directory_labels(list(dict.fromkeys(item.group for item in directories)))
    runs: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    native: dict[tuple[Any, ...], Chart] = {}
    combinations: dict[tuple[str, Path | None], str] = {}
    repetitions: dict[tuple[str, str], list[dict[str, Any]]] = {}
    available_methods: set[str] = set()
    method_filters: dict[Path, tuple[str, ...]] = {}
    observed: set[Path] = set()
    plans: dict[Path, list[_RecordedRun]] = {}
    for source in directories:
        context = json.loads(source.context.read_text()) if source.context is not None else {}
        command = source.context.parent.parent if source.context is not None else None
        iteration = command.parent.parent if command is not None and command.parent.name == "runs" else None
        identity = {
            "source": str(source.directory), "label": labels[source.group],
            "iteration": iteration.name if iteration is not None else None,
            "run": command.name if command is not None else source.directory.name,
            "status": context.get("status"), "exit_code": context.get("exit_code"),
            "command": context.get("command"),
            "context": str(source.context) if source.context is not None else None,
        }
        found = False
        for saved in _selected_runs(source.directory, context, plans):
            found = True
            result_path = saved.directory.resolve()
            if result_path in observed:
                continue
            observed.add(result_path)
            measured = saved.metrics or {}
            for kind in ("distribution_comparison", "greedy_comparison"):
                if kind in measured:
                    protocol = measured[kind].get("protocol")
                    if protocol is not None:
                        saved.conditions["protocol"] = protocol
                    else:
                        saved.conditions.setdefault("unknown", []).append("protocol")
                    if measured[kind].get("reference_model") is not None:
                        saved.conditions["reference_model"] = measured[kind]["reference_model"]
                    else:
                        saved.conditions.setdefault("unknown", []).append("reference_model")
            comparison = comparison_charts(measured)
            charts = []
            if comparison is not None:
                charts, identities = comparison
            elif "scores" in measured:
                charts, identities = _quality_charts(measured), [saved.method]
            elif (saved.directory / "slo_results.json").is_file():
                charts = _slo_charts(json.loads((saved.directory / "slo_results.json").read_text()))
                identities = [saved.method]
            else:
                identities = [saved.method]
            available_methods.update(identities)
            chosen = [method for method in identities if not methods or method in methods]
            if not chosen:
                continue
            if comparison is not None and methods:
                method_filters[saved.directory] = tuple(chosen)
            label = labels[source.group] + (f" / {saved.method}" if saved.method != "default" else "")
            # Missing workload configuration is unknown, not equal to another run's.
            fixed = (json.dumps(saved.conditions, sort_keys=True),
                     saved.directory if saved.configuration is None or saved.conditions.get("unknown") else None)
            combination = combinations.setdefault(fixed, f"workload-{len(combinations) + 1}")
            runs.append({**identity, "method": saved.method, "methods": chosen,
                         "result": str(saved.directory), "measured": saved.metrics is not None or bool(charts),
                         "started": saved.started, "measurement_exit_code": saved.exit_code,
                         "config": str(saved.configuration) if saved.configuration is not None else None,
                         "conditions": saved.conditions,
                         "environment": next((str(path) for name in ("environment.json", "serving_environments.json")
                                              if (path := saved.directory / name).is_file()), None),
                         **{key: measured.get(key) for key in ("request_num", "success_num", "failed_num")}})
            if charts:
                for chart in charts:
                    series = []
                    for item in chart.series:
                        method = str(item.records[0].get("method") or item.name) if comparison is not None else saved.method
                        if method not in chosen:
                            continue
                        method_label = labels[source.group] + (f" / {method}" if method != "default" else "")
                        name = method_label
                        if command is not None and source.group != command:
                            name += f" / {command.name}"
                        if comparison is not None and item.name != method:
                            name += f" / {item.name}"
                        series.append(replace(item, name=name, records=tuple(
                            {**row, "method": method_label, "result": str(saved.directory)}
                            for row in item.records
                        )))
                    if not series:
                        continue
                    key = (chart.name, chart.title, chart.ylabel, chart.tick_labels, fixed)
                    if key in native:
                        native[key] = replace(native[key], series=native[key].series + tuple(series))
                    else:
                        native[key] = replace(chart, name=f"comparison-{combination}-{chart.name}", series=tuple(series))
            else:
                repetitions.setdefault((label, combination), []).append(runs[-1])
                points.append({**measured, "combination": combination,
                               "parameter_group": str(saved.conditions.get("mode", "performance")),
                               "bench": {**saved.conditions, "service": {"name": label}},
                               "exit_code": saved.exit_code})
        if not found and not methods:
            runs.append({**identity, "result": None, "measured": False})
    unknown = set(methods) - available_methods
    if unknown:
        raise ValueError("Unknown plot methods: " + ", ".join(sorted(unknown)))
    from benchmarks.sweeps.core import summarize_sweep

    _comparison_details(runs)
    details = {run["result"]: {key: value for key, value in run.items() if key in (
        "conditions_changes", "conditions_unknown", "environment_changes", "environment_unknown",
    )} for run in runs if run.get("result")}
    for key, chart in native.items():
        native[key] = replace(chart, series=tuple(replace(series, records=tuple(
            {**record, **details[record["result"]]} for record in series.records
        )) for series in chart.series))
    summary = summarize_sweep(points)
    for row in summary:
        repeated = repetitions[row["method"], row["combination"]]
        row.update(
            runs=sum(record["started"] for record in repeated), requested_runs=len(repeated),
            failed_runs=sum(bool(record["measurement_exit_code"]) or bool(record.get("failed_num")) for record in repeated),
        )
        for section in ("conditions", "environment"):
            row[f"{section}_changes"] = {
                record["result"]: record[f"{section}_changes"] for record in repeated if record[f"{section}_changes"]
            }
            row[f"{section}_unknown"] = sorted({
                field for record in repeated for field in record[f"{section}_unknown"]
            })
    return SavedResults(runs, points, summary, list(native.values()), method_filters)
