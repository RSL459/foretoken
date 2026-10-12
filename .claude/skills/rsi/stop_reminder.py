# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Manage a one-shot RSI Stop reminder for the invoking Claude Code session."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

STATE_DIRECTORY = Path(__file__).resolve().parents[3] / "results" / "rsi-sessions"


def session_path(session_id: str) -> Path:
    """Locate this session's reminder without allowing paths as session IDs."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        raise ValueError("Expected a harness session ID, not a path")
    return STATE_DIRECTORY / f"{session_id}.json"


def parse_deadline(value: str) -> datetime:
    """Parse a task deadline with an explicit timezone for cross-host comparisons."""
    deadline = datetime.fromisoformat(value)
    if deadline.tzinfo is None:
        raise ValueError("Task deadline must include a UTC offset")
    return deadline


def consume(path: Path) -> dict | None:
    """Read and remove the reminder; absence means this session is not armed."""
    try:
        state = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    path.unlink()
    return state


def check() -> None:
    """Return at most one Stop continuation without calling a model or scheduler."""
    event = json.load(sys.stdin)
    state = consume(session_path(event["session_id"]))
    if state is None or event.get("stop_hook_active", False):
        return
    deadline = state["deadline"]
    if deadline is not None and datetime.now().astimezone() >= parse_deadline(deadline):
        return
    # An exit-zero decision gives one reminder and lets once:true unregister it.
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "The RSI execution reminder is still armed. Check the current user "
                    "request and task state. If execution is active, process completed "
                    "worker results and continue useful work within the task's parallelism "
                    "requirements; inspect any experiment-efficiency warnings. If the "
                    "user paused or stopped, the task is complete, or outside intervention "
                    "is required, honor that state and finish the appropriate cleanup "
                    "and report. This reminder is consumed; do not rearm it as a timer."
                ),
            }
        )
    )


def main() -> None:
    """Arm, disarm, or consume the hook's session-local reminder from the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    arm = commands.add_parser("arm", help="Arm the current RSI execution's reminder")
    arm.add_argument("session_id")
    arm.add_argument("--deadline", type=parse_deadline)
    disarm = commands.add_parser("disarm", help="Remove this session's reminder")
    disarm.add_argument("session_id")
    commands.add_parser("check", help="Read a Claude Code Stop event from stdin")
    args = parser.parse_args()

    if args.command == "check":
        check()
    elif args.command == "disarm":
        consume(session_path(args.session_id))
    else:
        path = session_path(args.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "deadline": args.deadline.isoformat() if args.deadline else None,
                }
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
