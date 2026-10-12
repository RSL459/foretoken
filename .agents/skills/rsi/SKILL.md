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

Create one native background supervisor with the task, complete node list, experiment directory, deadline, and resource ownership. It owns observation, analysis, and any task-local GPU collectors it starts; deployments and worker scheduling remain with the main agent. Exclude the supervisor from the working-subagent count. Supply the following instructions:

- Keep GPU collection continuous across deployment, measurement, and result analysis. Reuse existing telemetry with retained history covering the assigned GPUs on every task node. Where coverage is missing, start a persistent collector using the installed device tools, record its process identity and output location, and verify that timestamped samples continue to arrive. Reuse a running collector rather than starting one for each analysis window.
- Record the sampling interval separately from the analysis interval. Append samples with node, GPU identity, timestamp, and utilization to the experiment's raw records. Record collection failures and gaps explicitly; missing samples are unknown, not zero. Collection must continue while you analyze results, send messages, or wait for a response.
- Periodically read newly completed time windows and compute per-node means, idle durations, and sampling coverage in the shell. Use bounded reads or waits within the shell tool's timeout; these consume the continuous data stream rather than restarting collection. Track the last analyzed timestamp so windows are not repeatedly processed. Keep normal summaries in your own context and continue observation without finishing after every window. Do not schedule periodic prompts for the main agent.
- Check sample freshness as part of each analysis. If collection stops, inspect its process and errors, restore the task-owned collector after confirming the previous instance has exited, and record the gap. If the harness cannot sustain independent analysis, report that limitation once; preserve the collector's recorded identity so the main agent can manage its lifecycle.
- Correlate GPU activity with actual commands, elapsed time, logs, run records, candidate readiness, and pending result analysis. Look for unused nodes, avoidable rebuilds or downloads, stalled commands, repeated measurements without a question, and completed measurements awaiting analysis. Preserve isolated comparison windows and the task's measurement requirements.
- Notify the main agent only when action is needed, with the observed facts, evidence location, and recommended action. Use a native parent-message tool when available. If the harness only delivers worker completion results, return the actionable finding through that channel; the main agent should handle it and resume this supervisor's context. Do not send routine status reports or repeat an unchanged warning. Check whether the action was taken in subsequent windows.
- Give task-owned collectors the task deadline and an explicit stop mechanism so they can exit without waiting for a model decision. On pause, stop, or completion, stop those collectors, verify their exit, and return observation coverage and GPU utilization evidence. Keep reused monitoring services running; their lifecycle belongs to their existing owner.

Keep worker reassignment in the native completion flow above; the supervisor does not maintain a second worker registry or infer agent counts from GPU usage. Do not require CPU utilization or memory occupancy reports.

## Pause or finish

A user pause or stop takes precedence over queued completion messages and supervisor suggestions. Stop assigning experiments, tell workers and the supervisor to stop, and verify their owned processes have stopped; use native cancellation if needed. Preserve resumable work on pause. On completion, clean up resources with no remaining consumer after checking ownership and preserving required evidence.

Follow the task's delivery paths and the [experiment records guide](../../../rsi-playbooks/experiment-records.md). Report retained changes, measured results, GPU sampling coverage, and unresolved blockers. Do not present the skill's instructions as evidence that experiments or supervision actually ran.
