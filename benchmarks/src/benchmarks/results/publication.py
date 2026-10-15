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
RECORDING_LOCK = "wandb-recording.lock"


def write_publication_state(path: Path, value: dict[str, Any]) -> None:
    """Replace a publication record atomically while readers inspect the result directory."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def recording_active(directory: Path) -> bool:
    """Observe the result owner's lifetime without waiting for measurement or log cleanup."""
    try:
        lock = (directory / RECORDING_LOCK).open("r")
    except FileNotFoundError:
        return False
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


class WandbSink:
    """Record upload inputs locally while an independent publisher follows the progress journal."""

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
            "exit_code": None,
        }
        self.history: RequestRecordWriter | None = None

    def open(self, record: dict[str, Any]) -> None:
        """Expose the run identity and journal before measurement, without opening a remote session."""
        self.history = RequestRecordWriter(self.directory / HISTORY_FILE)
        write_publication_state(self.directory / PUBLICATION_FILE, self.job)

    def log_progress(self, row: dict[str, Any], *, axis: str) -> None:
        """Retain each chart snapshot on its original measurement axis for live upload and replay."""
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
        """Seal the progress journal and publish the final result references for the uploader."""
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
    """Find active and completed publication records under selected result directories once."""
    jobs: set[Path] = set()
    for source in sources:
        source = source.resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"Result directory does not exist: {source}")
        jobs.update(source.rglob(PUBLICATION_FILE))
    return sorted(jobs)


def start_publication(directory: Path) -> None:
    """Start one independent publisher that follows an enclosing measurement and its child runs."""
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


def _publish_job(job: Path, deadline: float) -> tuple[bool, float]:
    """Serialize one run's publishers and bound SDK work without charging measurement waits."""
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
                if time.monotonic() >= deadline:
                    print("Publication deadline reached while waiting for another publisher.", flush=True)
                    return False, deadline
                started = time.monotonic()
                time.sleep(0.2)
                status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
                if status.get("waiting_for_measurement"):
                    deadline += time.monotonic() - started
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.is_file() else {}
        if status.get("state") == "published":
            print(f"Already published: {status.get('url') or directory}", flush=True)
            return True, deadline
        status.update(state="uploading", waiting_for_measurement=False)
        status.pop("error", None)
        write_publication_state(status_path, status)
        log_path = directory / "wandb-publish.log"
        print(f"Publishing {directory}; log: {log_path}", flush=True)
        error = None
        # SDK calls and teardown are bounded by the parent process. Waiting for
        # new local measurements is not network work and may span a long run.
        try:
            with (
                log_path.open("a", encoding="utf-8") as log,
                subprocess.Popen(
                    [sys.executable, "-m", "benchmarks.results.wandb_upload", str(job)],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    pass_fds=(lock.fileno(),),
                ) as process,
            ):
                try:
                    previous = time.monotonic()
                    reported_url = None
                    while process.poll() is None:
                        time.sleep(0.2)
                        now = time.monotonic()
                        status = json.loads(status_path.read_text(encoding="utf-8"))
                        if status.get("url") and status["url"] != reported_url:
                            reported_url = status["url"]
                            print(f"W&B results: {reported_url}", flush=True)
                        if status.get("waiting_for_measurement"):
                            deadline += now - previous
                        previous = now
                        if now >= deadline and process.poll() is None:
                            process.kill()
                            process.wait()
                            error = f"Publication timed out; see {log_path}"
                            break
                    if error is None and process.returncode:
                        error = f"Publisher exited with status {process.returncode}; see {log_path}"
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
        except OSError as failure:
            error = str(failure)
        except BaseException:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status.update(state="pending", error="Publication interrupted")
            status.pop("waiting_for_measurement", None)
            write_publication_state(status_path, status)
            raise
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status.pop("waiting_for_measurement", None)
        if error is not None:
            status.update(state="pending", error=error)
            print(error, flush=True)
        else:
            status.update(state="published")
            status.pop("error", None)
            print(f"Published: {status['url']}", flush=True)
        write_publication_state(status_path, status)
        return error is None, deadline


def publish_results(sources: tuple[Path, ...], *, timeout: float) -> bool:
    """Follow local result owners, publishing each run once without holding up measurement."""
    sources = tuple(source.resolve() for source in sources)
    if not publication_jobs(sources):
        raise ValueError("No saved W&B publications found; record results with --output wandb")
    deadline = time.monotonic() + timeout
    attempted: set[Path] = set()
    succeeded = True
    while True:
        idle_started = time.monotonic()
        # Observe owner lifetimes before discovering jobs, so a final child
        # created during cleanup is included before the enclosing scope ends.
        active = any(recording_active(source) for source in sources)
        jobs = publication_jobs(sources)
        for job in jobs:
            recording = recording_active(job.parent)
            active = active or recording
            if job in attempted:
                continue
            if recording and (job.parent / HISTORY_FILE).stat().st_size == 0:
                continue
            deadline += time.monotonic() - idle_started
            if time.monotonic() >= deadline:
                print("Publication deadline reached; remaining runs are pending.", flush=True)
                return False
            completed, deadline = _publish_job(job, deadline)
            idle_started = time.monotonic()
            succeeded = completed and succeeded
            attempted.add(job)
        # An ancestor selection has no recording lock of its own. Its running
        # children may have added jobs while an earlier upload was in progress.
        if not active and set(publication_jobs(sources)).issubset(attempted):
            return succeeded
        # No remote operation is pending between discovery passes.
        time.sleep(0.2)
        deadline += time.monotonic() - idle_started
