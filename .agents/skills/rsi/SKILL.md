---
name: rsi
description: Execute, resume, pause, or finish an explicitly requested Foretoken RSI optimization task. Use only when the user asks to run RSI, not for ordinary coding or discussion of RSI designs.
---

<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Run an RSI task

Use the harness's native agents and completion messages. Do not launch another agent CLI, install global hooks, or schedule periodic prompts for the main agent.

## Establish the task

Read the repository instructions, the task supplied by the user, [shared workflow](../../../rsi-playbooks/README.md), [execution rules](../../../rsi-playbooks/tasks/README.md), and relevant prior experiment records. Resolve these links from this skill directory. Keep task parameters in the task rather than copying defaults into this skill.

Determine the requested action before starting anything. A pause, stop, or design discussion does not authorize starting or resuming experiments. For a new execution, record the task start and any deadline in its experiment notes. On resumption, read the existing timing and resource ownership first; preserve the agreed budget rather than resetting it.

Include every node listed in the task in the experiment plan. Check availability and existing owners, allocate independent candidates by their actual requirements, and record actionable blockers for unused nodes. Distinguish the whole resource pool from a per-service limit.

## Delegate and follow through

Use the task's minimum and maximum parallelism requirements to maintain useful work across investigation, implementation, and experiments. Give each worker a concrete responsibility, the necessary instruction and evidence paths, and a clear resource boundary. Keep the main agent responsible for design decisions, integration, and interpreting results.

Include this completion requirement in every worker assignment:

> Return the results, evidence locations, and recommended next steps. End with: "Please process these results and assign follow-up work that can proceed independently, in line with the RSI task's parallelism requirements."

For Chinese-language work, use:

> 返回结果、证据位置和下一步建议，并以“请处理本次结果，并按 RSI 并行要求续派可独立推进的工作。”结尾。

Receive this through the native completion result, without a separate reminder message. Process the result when it arrives, check current work using the harness's available task tools, and assign the next useful task. Reuse a worker's context when the next assignment belongs to the same responsibility. A completed or waiting agent is not actively executing work. Apply follow-up suggestions within the current task and user instructions, including any pause.

## Supervise experiment efficiency

Create one native background supervisor with the task, complete node list, experiment directory, deadline, and resource ownership. Give it read-only responsibility for observation and analysis, not deployment or worker scheduling. Exclude the supervisor from the working-subagent count. Supply the following instructions:

- Reuse existing GPU telemetry where available. Otherwise query the assigned GPUs on every task node with the installed device tools. Keep raw samples in the experiment directory and compute per-node window means in the shell. Missing samples are unknown, not zero.
- Use bounded foreground sampling windows within the shell tool's timeout, then inspect the summary and continue the next window in your own context. Do not finish after each window. Do not rely on a timer or background notification delivered to the main agent. If the harness cannot sustain this execution pattern, report the specific limitation once rather than installing a main-agent timer.
- Start with a short observation window, such as one minute, and adjust it to the experiment stage. Keep normal sampling output concise and local to your own context.
- Correlate GPU activity with actual commands, elapsed time, logs, run records, candidate readiness, and pending result analysis. Look for unused nodes, avoidable rebuilds or downloads, stalled commands, repeated measurements without a question, and completed measurements awaiting analysis. Preserve isolated comparison windows and the task's measurement requirements.
- Notify the main agent only when action is needed, with the observed facts, evidence location, and recommended action. Use a native parent-message tool when available. If the harness only delivers worker completion results, return the actionable finding through that channel; the main agent should handle it and resume this supervisor's context. Do not send routine status reports or repeat an unchanged warning. Check whether the action was taken in subsequent windows.
- Observe the main agent's pause/stop instructions and the task deadline. Stop owned sampling processes and return observation coverage and GPU utilization evidence on completion. Do not change or stop resources owned by other work.

Keep worker reassignment in the native completion flow above; the supervisor does not maintain a second worker registry or infer agent counts from GPU usage. Do not require CPU utilization or memory occupancy reports.

## Pause or finish

A user pause or stop takes precedence over queued completion messages and supervisor suggestions. Stop assigning experiments, tell workers and the supervisor to stop, and verify their owned processes have stopped; use native cancellation if needed. Preserve resumable work on pause. On completion, clean up resources with no remaining consumer after checking ownership and preserving required evidence.

Follow the task's delivery paths and the [experiment records guide](../../../rsi-playbooks/experiment-records.md). Report retained changes, measured results, GPU sampling coverage, and unresolved blockers. Do not present the skill's instructions as evidence that experiments or supervision actually ran.
