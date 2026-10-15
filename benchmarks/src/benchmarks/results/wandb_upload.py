# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Replay one saved benchmark into W&B in a process owned by the publication supervisor."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import wandb

from benchmarks.results.output import BenchmarkRun
from benchmarks.results.publication import HISTORY_FILE, STATUS_FILE, write_publication_state
from benchmarks.results.records import load_http_measurements


class _ReplayRun:
    """Own deterministic history steps and artifact acknowledgements for a resumed SDK run."""

    def __init__(self, run: Any) -> None:
        self.run = run
        self.step = 0
        self.resume_step = run.step
        self.artifacts: list[Any] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.run, name)

    def log(self, values: dict[str, Any]) -> None:
        """Replay a stable row sequence, skipping history already accepted by the remote run."""
        if self.step >= self.resume_step:
            self.run.log(values, step=self.step)
        self.step += 1

    def log_artifact(self, artifact: Any) -> Any:
        """Queue an artifact and retain its acknowledgement before marking publication complete."""
        artifact = self.run.log_artifact(artifact)
        self.artifacts.append(artifact)
        return artifact

    def finish(self, exit_code: int) -> None:
        """Wait for every artifact before finishing the run with its original measurement status."""
        for artifact in self.artifacts:
            artifact.wait()
        self.run.finish(exit_code=exit_code)


def _publish_result(session: _ReplayRun, result: BenchmarkRun) -> None:
    """Select the existing domain presenter from the recorded benchmark mode."""
    mode = result.record["mode"]
    if mode in {"http_load", "arrival_trace"}:
        from benchmarks.results.wandb import publish_http_wandb

        publish_http_wandb(session, result)
    elif mode in {"parameter_sweep", "video_parameter_sweep"}:
        from benchmarks.results.wandb import publish_sweep_wandb

        publish_sweep_wandb(session, result)
    elif mode == "slo_search":
        from benchmarks.results.wandb import publish_slo_wandb

        publish_slo_wandb(session, result)
    elif mode == "video_generation":
        from benchmarks.results.video_wandb import publish_video_wandb

        publish_video_wandb(session, result)
    elif mode == "evaluation":
        from benchmarks.results.evaluation import publish_quality_wandb

        publish_quality_wandb(session, result)
    elif mode == "evaluation_comparison":
        from benchmarks.results.evaluation import publish_evaluation_comparison_wandb

        publish_evaluation_comparison_wandb(session, result)
    elif mode == "distribution_comparison":
        from benchmarks.results.distribution_comparison import publish_distribution_comparison_wandb

        publish_distribution_comparison_wandb(session, result)
    elif mode == "greedy_comparison":
        from benchmarks.results.distribution_comparison import publish_greedy_comparison_wandb

        publish_greedy_comparison_wandb(session, result)
    else:
        raise ValueError(f"Unsupported benchmark publication mode: {mode}")


def upload(job_path: Path) -> None:
    """Publish retained records without accessing a model service or changing measurement evidence."""
    job = json.loads(job_path.read_text(encoding="utf-8"))
    if job["version"] != 1:
        raise ValueError(f"Unsupported publication version: {job['version']}")
    directory = job_path.parent
    status_path = directory / STATUS_FILE
    status = json.loads(status_path.read_text(encoding="utf-8"))
    options = {
        "id": job["id"],
        "project": job["project"],
        "name": job["name"],
        "config": job["config"],
        "dir": str(directory),
        "mode": "online",
        "resume": "allow",
        # Upload process activity is not benchmark-client resource usage.
        "settings": wandb.Settings(silent=True, console="off", x_disable_stats=True),
    }
    entity = status.get("entity") or job["entity"]
    if entity:
        options["entity"] = entity
    if job["group"]:
        options["group"] = job["group"]
    sdk_run = wandb.init(**options)
    if sdk_run is None:
        raise RuntimeError("W&B initialization returned no run")
    status.update(entity=sdk_run.entity, url=sdk_run.url)
    write_publication_state(status_path, status)
    print(f"W&B results: {sdk_run.url}", flush=True)
    session = _ReplayRun(sdk_run)

    # Replay the captured axes and row order rather than recomputing live windows
    # from completion records. Resume uses the same run ID and history step space.
    defined: set[tuple[str, str]] = set()
    with (directory / HISTORY_FILE).open(encoding="utf-8") as history:
        for line in history:
            event = json.loads(line)
            axis, row = event["axis"], event["values"]
            if (axis, axis) not in defined:
                session.define_metric(axis, hidden=True)
                defined.add((axis, axis))
            for key in sorted(row.keys() - {axis}):
                if (key, axis) not in defined:
                    session.define_metric(key, step_metric=axis, step_sync=False)
                    defined.add((key, axis))
            session.log(row)

    saved = job["result"]
    artifacts: dict[str, Path] = {}
    if saved is not None:
        artifacts = {name: directory / path for name, path in saved["artifacts"].items()}
        measurements = (
            load_http_measurements(json.loads(artifacts["raw_output"].read_text(encoding="utf-8")))
            if saved["measurements"] else None
        )
        result = BenchmarkRun(
            record=saved["record"],
            metrics=json.loads(artifacts["metrics"].read_text(encoding="utf-8")),
            measurements=measurements,
            artifacts=artifacts,
            exit_code=job["exit_code"],
            http_series_recorded=saved["http_series_recorded"],
        )
        _publish_result(session, result)
        if "warmup_metrics" in artifacts:
            artifact = wandb.Artifact(f"warmup-{session.id}", type="benchmark-warmup")
            for name in ("warmup_metrics", "warmup_raw_output"):
                artifact.add_file(str(artifacts[name]), name=artifacts[name].name)
            session.log_artifact(artifact)
        if "plots" in artifacts:
            artifact = wandb.Artifact(f"plots-{session.id}", type="benchmark-plots")
            artifact.add_dir(str(artifacts["plots"]))
            session.log_artifact(artifact)

    for kind, names in job["journals"].items():
        artifact = wandb.Artifact(f"{kind}-{session.id}", type=f"benchmark-{kind}")
        for name in names:
            artifact.add_file(str(directory / name), name=name)
        session.log_artifact(artifact)
    artifact = wandb.Artifact(f"logs-{session.id}", type="benchmark-logs")
    artifact.add_file(str(directory / "run.log"), name="run.log")
    session.log_artifact(artifact)
    session.finish(job["exit_code"])


if __name__ == "__main__":
    upload(Path(sys.argv[1]))
