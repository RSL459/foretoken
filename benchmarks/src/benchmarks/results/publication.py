# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Retain W&B publication inputs and supervise uploads independently of measurement."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from benchmarks.config.benchmark import WandbRunConfig
from benchmarks.results.console import print_result_location
from benchmarks.results.records import RequestRecordWriter

if TYPE_CHECKING:
    from benchmarks.results.output import BenchmarkRun

logger = logging.getLogger(__name__)
PUBLICATION_FILE = "wandb-publication.json"
STATUS_FILE = "wandb-status.json"
HISTORY_FILE = "wandb-history.jsonl"


def write_publication_state(path: Path, value: dict[str, Any]) -> None:
    """Replace a publication record atomically while readers inspect the result directory."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class WandbSink:
    """Record upload inputs locally; the enclosing result lifecycle starts network publication."""

    def __init__(
        self,
        config: WandbRunConfig,
        *,
        execution_dir: str,
        run_name: str,
        group: str,
        run_config: dict[str, Any],
    ) -> None:
        self.directory = Path(execution_dir).resolve()
        self.job: dict[str, Any] = {
            "version": 1,
            "id": uuid.uuid4().hex,
            "project": config.project,
            "entity": config.entity,
            "name": run_name,
            "group": group,
            "config": run_config,
            "result": None,
        }
        self.history: RequestRecordWriter | None = None

    def open(self, record: dict[str, Any]) -> None:
        """Open the progress journal without initializing a remote SDK session."""
        self.history = RequestRecordWriter(self.directory / HISTORY_FILE)

    def log_progress(self, row: dict[str, Any], *, axis: str) -> None:
        """Retain each chart snapshot on its original measurement axis for later replay."""
        if self.history is None:
            raise RuntimeError("W&B recording is not open")
        self.history.write({"axis": axis, "values": row})

    def publish(self, run: BenchmarkRun) -> None:
        """Reference finalized local artifacts instead of duplicating metrics or serializing SDK objects."""
        self.job["result"] = {
            "record": run.record,
            "artifacts": {
                name: os.path.relpath(path.resolve(), self.directory)
                for name, path in run.artifacts.items()
            },
            "measurements": run.measurements is not None,
            "http_series_recorded": run.http_series_recorded,
        }

    def close(self, *, exit_code: int = 0) -> None:
        """Make the run available for upload only after its local progress stream has closed."""
        if self.history is None:
            return
        self.history.close()
        self.history = None
        self.job["exit_code"] = exit_code
        journals: dict[str, list[str]] = {}
        for path in sorted(self.directory.glob("*.jsonl")):
            if path.name == HISTORY_FILE:
                continue
            kind = "responses" if path.name in {"responses.jsonl", "warmup_responses.jsonl"} else "records"
            journals.setdefault(kind, []).append(path.name)
        self.job["journals"] = journals
        write_publication_state(self.directory / PUBLICATION_FILE, self.job)


def publication_jobs(sources: tuple[Path, ...]) -> list[Path]:
    """Find finalized publication records under result, sweep, or experiment directories once."""
    jobs: set[Path] = set()
    for source in sources:
        source = source.resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"Result directory does not exist: {source}")
        jobs.update(source.rglob(PUBLICATION_FILE))
    return sorted(jobs)


def start_publication(directory: Path) -> None:
    """Start one detached, bounded uploader for an enclosing run without delaying the caller."""
    directory = directory.resolve()
    if not next(directory.rglob(PUBLICATION_FILE), None):
        return
    retry = f"foretoken publish {shlex.quote(str(directory))}"
    log_path = directory / "publication.log"
    try:
        with log_path.open("a", encoding="utf-8") as log:
            subprocess.Popen(
                [sys.executable, "-m", "benchmarks.publish", str(directory)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as error:
        logger.error("W&B publication is pending: %s. Retry with: %s", error, retry)
    else:
        print_result_location(f"W&B publication started; log: {log_path}\nRetry or wait for publication: {retry}")


def publish_results(jobs: list[Path], *, timeout: float) -> bool:
    """Upload saved runs within one deadline; retain failed jobs and serialize concurrent publishers."""
    deadline = time.monotonic() + timeout
    succeeded = True
    for job in jobs:
        directory = job.parent
        status_path = directory / STATUS_FILE
        with (directory / "wandb-publication.lock").open("a") as lock:
            waiting = False
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if not waiting:
                        print(f"Waiting for active publication: {directory}", flush=True)
                        waiting = True
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        print("Publication deadline reached while waiting for another publisher.", flush=True)
                        return False
                    time.sleep(min(0.2, remaining))
            status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
            if status.get("state") == "published":
                print(f"Already published: {status.get('url') or directory}", flush=True)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print("Publication deadline reached; remaining runs are pending.", flush=True)
                return False
            status.update(state="uploading")
            status.pop("error", None)
            write_publication_state(status_path, status)
            log_path = directory / "wandb-publish.log"
            print(f"Publishing {directory}; log: {log_path}", flush=True)
            error = None
            # SDK retries and teardown can outlast their individual request
            # timeouts. The supervisor owns the deadline and reaps the worker.
            try:
                with log_path.open("a", encoding="utf-8") as log:
                    result = subprocess.run(
                        [sys.executable, "-m", "benchmarks.results.wandb_upload", str(job)],
                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                        timeout=remaining, check=False, pass_fds=(lock.fileno(),),
                    )
                if result.returncode:
                    error = f"Publisher exited with status {result.returncode}; see {log_path}"
            except subprocess.TimeoutExpired:
                error = f"Publication timed out; see {log_path}"
            except OSError as failure:
                error = str(failure)
            except BaseException:
                status = json.loads(status_path.read_text(encoding="utf-8"))
                status.update(state="pending", error="Publication interrupted")
                write_publication_state(status_path, status)
                raise
            # The worker records the resolved remote identity. Its exit includes
            # artifact acknowledgements, run.finish(), and SDK process teardown.
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if error is not None:
                status.update(state="pending", error=error)
                succeeded = False
                print(error, flush=True)
            else:
                status.update(state="published")
                status.pop("error", None)
                print(f"Published: {status['url']}", flush=True)
            write_publication_state(status_path, status)
    return succeeded
