# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Continuously collect host GPU usage and summarize retained time windows."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import signal
import socket
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path


def timestamp(value: str) -> float:
    """Parse an offset-aware ISO timestamp used for task deadlines and windows."""
    date = datetime.fromisoformat(value)
    if date.tzinfo is None:
        raise argparse.ArgumentTypeError("Include a UTC offset in the timestamp")
    return date.timestamp()


def positive_seconds(value: str) -> float:
    """Reject nonpositive or nonfinite collection intervals at the CLI boundary."""
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive number of seconds")
    return number


def utilization(value: str | float) -> float | None:
    """Normalize a device reading, retaining unavailable counters as missing."""
    if str(value).strip() in {"N/A", "[N/A]", "[Not Supported]"}:
        return None
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ValueError(f"Invalid GPU utilization: {value!r}")
    return number


def query_gpus(backend: str, indices: list[int] | None, timeout: float) -> list[dict]:
    """Read host device counters through the selected vendor's read-only CLI."""
    if backend == "nvidia":
        command = [
            "nvidia-smi",
            "--query-gpu=index,uuid,utilization.gpu",
            "--format=csv,noheader,nounits",
        ]
    else:
        command = ["mx-smi", "--show-usage", "--json"]
    if indices is not None:
        command.extend(["-i", ",".join(map(str, indices))])
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or f"{command[0]} exited {result.returncode}"
        )
    readings = []
    if backend == "nvidia":
        for row in csv.reader(result.stdout.splitlines()):
            index, identity, usage = row
            readings.append(
                {
                    "index": int(index),
                    "id": identity.strip(),
                    "utilization_percent": utilization(usage),
                }
            )
    else:
        text = result.stdout.strip()
        # mx-smi prints a version banner before its JSON on supported hosts.
        if text.startswith("mx-smi  version:"):
            text = text.split("\n", 1)[1]
        devices = json.loads(text)
        for identity, device in devices.items():
            if isinstance(device, dict) and "device_id" in device:
                readings.append(
                    {
                        "index": int(device["device_id"]),
                        "id": identity,
                        "utilization_percent": utilization(device["utilization"]),
                    }
                )
    if not readings:
        raise ValueError("Device query returned no GPUs")
    if indices is not None and set(indices) != {row["index"] for row in readings}:
        raise ValueError("Device query did not return the requested GPU indices")
    return readings


def collect(args: argparse.Namespace) -> None:
    """Own one foreground collector; persist samples until deadline, signal, or stop file."""
    backend = args.backend
    if backend == "auto":
        if shutil.which("nvidia-smi"):
            backend = "nvidia"
        elif shutil.which("mx-smi"):
            backend = "metax"
        else:
            raise ValueError("Neither nvidia-smi nor mx-smi is available")
    if args.deadline is not None and args.deadline <= time.time():
        raise ValueError("Task deadline has already passed")
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if (output / "stop").exists():
        raise ValueError("Use a new output directory when resuming collection")
    stopped = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda _signum, _frame: stopped.set())

    # Exclusive creation prevents duplicate collectors and preserves earlier runs.
    with (output / "samples.jsonl").open("x", buffering=1) as stream:

        def emit(record: dict) -> None:
            stream.write(json.dumps(record, allow_nan=False) + "\n")

        emit(
            {
                "event": "start",
                "timestamp": time.time(),
                "node": socket.gethostname(),
                "pid": os.getpid(),
                "backend": backend,
                "interval_seconds": args.interval,
                "gpu_indices": args.gpus,
                "deadline": args.deadline,
            }
        )
        print(
            json.dumps({"pid": os.getpid(), "output": str(output.resolve())}),
            flush=True,
        )
        reason = "failed"
        try:
            while not stopped.is_set() and not (output / "stop").exists():
                now = time.time()
                remaining = (
                    args.deadline - now if args.deadline is not None else math.inf
                )
                if remaining <= 0:
                    reason = "deadline"
                    break
                tick = time.monotonic()
                record = {"event": "sample", "timestamp": now, "gpus": []}
                try:
                    record["gpus"] = query_gpus(
                        backend, args.gpus, min(10.0, remaining)
                    )
                except (
                    OSError,
                    subprocess.TimeoutExpired,
                    RuntimeError,
                    ValueError,
                ) as exc:
                    record["error"] = str(exc)
                emit(record)
                next_tick = tick + args.interval
                while not stopped.is_set() and not (output / "stop").exists():
                    delay = next_tick - time.monotonic()
                    if args.deadline is not None:
                        delay = min(delay, args.deadline - time.time())
                    if delay <= 0:
                        break
                    stopped.wait(min(delay, 1.0))
            if reason == "failed":
                reason = "stopped"
        finally:
            emit({"event": "end", "timestamp": time.time(), "reason": reason})


def summarize_run(directory: Path, since: float, until: float) -> dict:
    """Integrate one collector's samples, capping each reading at its sampling interval."""
    devices: dict[str, dict] = {}
    previous = None
    errors = []
    end = None
    last_sample = None
    last_success = None

    with (directory / "samples.jsonl").open() as stream:
        first = stream.readline()
        if not first.endswith("\n"):
            raise ValueError(f"Collector metadata is not yet complete: {directory}")
        metadata = json.loads(first)
        if metadata["event"] != "start":
            raise ValueError(f"Missing collector start record: {directory}")
        interval = metadata["interval_seconds"]

        def integrate(record: dict | None, next_time: float) -> None:
            if record is None:
                return
            start = max(since, record["timestamp"])
            stop = min(until, next_time, record["timestamp"] + interval)
            if stop <= start:
                return
            for gpu in record["gpus"]:
                state = devices[gpu["id"]]
                usage = gpu["utilization_percent"]
                if usage is not None:
                    duration = stop - start
                    state["covered_seconds"] += duration
                    state["weighted_usage"] += usage * duration
                    if usage == 0:
                        state["idle_seconds"] += duration

        for line in stream:
            # A live writer may have only appended part of its last record.
            if not line.endswith("\n"):
                break
            record = json.loads(line)
            stamp = record["timestamp"]
            integrate(previous, stamp)
            if stamp > until:
                previous = None
                break
            if record["event"] == "end":
                end = record
                previous = None
                break
            previous = record
            last_sample = stamp
            for gpu in record["gpus"]:
                devices.setdefault(
                    gpu["id"],
                    {
                        "id": gpu["id"],
                        "index": gpu["index"],
                        "covered_seconds": 0.0,
                        "idle_seconds": 0.0,
                        "weighted_usage": 0.0,
                    },
                )
            if record["gpus"] and any(
                gpu["utilization_percent"] is not None for gpu in record["gpus"]
            ):
                last_success = stamp
            if "error" in record and stamp >= since:
                errors.append({"timestamp": stamp, "message": record["error"]})
        integrate(previous, until)

    window = until - since
    covered = sum(device["covered_seconds"] for device in devices.values())
    weighted = sum(device["weighted_usage"] for device in devices.values())
    expected_indices = metadata["gpu_indices"]
    device_count = max(len(devices), len(expected_indices or []))
    for device in devices.values():
        duration = device["covered_seconds"]
        device["mean_utilization_percent"] = (
            device.pop("weighted_usage") / duration if duration else None
        )
        device["coverage_percent"] = 100 * duration / window
    return {
        "node": metadata["node"],
        "pid": metadata["pid"],
        "backend": metadata["backend"],
        "output": str(directory),
        "started_at": metadata["timestamp"],
        "end": end,
        "last_sample_at": last_sample,
        "last_success_at": last_success,
        "requested_gpu_indices": expected_indices,
        "mean_utilization_percent": weighted / covered if covered else None,
        "coverage_percent": 100 * covered / (window * device_count)
        if device_count
        else None,
        "gpus": list(devices.values()),
        "errors": errors,
    }


def main() -> None:
    """Expose collection, non-mutating window summaries, and cooperative stop requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect_parser = commands.add_parser(
        "collect", help="Continuously collect this host's GPUs"
    )
    collect_parser.add_argument(
        "--output", type=Path, required=True, help="New run directory"
    )
    collect_parser.add_argument(
        "--backend", choices=("auto", "nvidia", "metax"), default="auto"
    )
    collect_parser.add_argument(
        "--gpus",
        type=lambda value: list(dict.fromkeys(int(item) for item in value.split(","))),
        help="Comma-separated host GPU indices; default: all visible GPUs",
    )
    collect_parser.add_argument(
        "--interval",
        type=positive_seconds,
        default=10.0,
        help="Sampling interval in seconds (default: 10)",
    )
    collect_parser.add_argument(
        "--deadline", type=timestamp, help="Absolute task deadline with UTC offset"
    )
    summary_parser = commands.add_parser(
        "summarize", help="Summarize retained samples without interrupting collection"
    )
    summary_parser.add_argument("directories", type=Path, nargs="+")
    summary_parser.add_argument("--since", type=timestamp, required=True)
    summary_parser.add_argument(
        "--until", type=timestamp, help="Window end; defaults to now"
    )
    stop_parser = commands.add_parser(
        "stop", help="Request a collector to stop; samples are preserved"
    )
    stop_parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "collect":
            collect(args)
        elif args.command == "stop":
            if not (args.directory / "samples.jsonl").is_file():
                raise ValueError(
                    "Collector samples.jsonl does not exist in this directory"
                )
            (args.directory / "stop").touch()
        else:
            until = args.until if args.until is not None else time.time()
            if until <= args.since or until > time.time():
                raise ValueError("Summary window must have since < until <= now")
            print(
                json.dumps(
                    {
                        "since": args.since,
                        "until": until,
                        "nodes": [
                            summarize_run(path, args.since, until)
                            for path in args.directories
                        ],
                    },
                    indent=2,
                    allow_nan=False,
                )
            )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
