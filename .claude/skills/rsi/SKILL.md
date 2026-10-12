---
name: rsi
description: Execute, resume, pause, or finish an explicitly requested Foretoken RSI optimization task. Use only when the user asks to run RSI, not for ordinary coding or discussion of RSI designs.
hooks:
  Stop:
    - hooks:
        - type: command
          command: python3
          args:
            - -I
            - ${CLAUDE_PROJECT_DIR}/.claude/skills/rsi/stop_reminder.py
            - check
          once: true
          timeout: 5
---

<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# RSI in Claude Code

Read and follow `${CLAUDE_PROJECT_DIR}/.agents/skills/rsi/SKILL.md`. It owns the task workflow, delegation, experiment-efficiency supervision, and cleanup. This adapter adds only a one-shot reminder if the main agent tries to finish while execution is still armed.

Current session: `${CLAUDE_SESSION_ID}`.

For an explicitly requested start or resume, arm the reminder after reading the task and its existing timing:

```bash
python3 -I "${CLAUDE_PROJECT_DIR}/.claude/skills/rsi/stop_reminder.py" arm "${CLAUDE_SESSION_ID}" --deadline "<task deadline with UTC offset>"
```

Use the actual absolute deadline recorded for this task, for example an ISO 8601 timestamp ending in `+00:00`. Omit `--deadline` only when the task has no time budget. Preserve the original deadline on resumption. Do not arm the reminder for a design discussion, pause, or completed task.

Before replying to a pause/stop request, or after completing the task or identifying a blocker that requires outside intervention, disarm the reminder:

```bash
python3 -I "${CLAUDE_PROJECT_DIR}/.claude/skills/rsi/stop_reminder.py" disarm "${CLAUDE_SESSION_ID}"
```

Disarming only removes the reminder state; follow the shared workflow to stop workers and sampling and to handle experiment resources. The hook consumes its state on the first Stop event and exits successfully even when it returns a continuation reminder, so Claude Code removes it through `once: true`. It is not a recurring scheduler. Continue the task through native worker results and your own execution loop; do not repeatedly invoke this skill to manufacture a stop-hook loop.
