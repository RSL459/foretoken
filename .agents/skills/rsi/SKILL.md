---
name: rsi
description: Execute, resume, pause, or finish an explicitly requested Foretoken RSI optimization task. Use only when the user asks to run RSI, not for ordinary coding or discussion of RSI designs.
---

<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Run an RSI task

Use the current harness's native delegation, messages, and completion notifications. In an interactive Claude Code session, use an Agent Team with the user's single lead `/goal`; in Codex, use the available native agent tools to carry out the same role protocol. Check actual session capabilities before assigning work: ordinary subagents are not an Agent Team, and Codex does not inherit Claude's Team or `/goal` facilities. Do not launch another agent CLI, change settings to enable teams, add custom hooks, or schedule periodic prompts for the lead.

## Establish the task

Read the repository instructions, the task supplied by the user, [shared workflow](../../../rsi-playbooks/README.md), [execution rules](../../../rsi-playbooks/tasks/README.md), and relevant prior experiment records. Resolve these links from this skill directory. Keep task parameters in the task rather than copying defaults into this skill.

Determine the requested action before starting anything. A pause, stop, or design discussion does not authorize starting or resuming experiments. For a new execution, record the task start and any deadline in its experiment notes. On resumption, read the existing timing and resource ownership first; preserve the agreed budget rather than resetting it.

Include every node listed in the task in the experiment plan. Check availability and existing owners, allocate independent candidates by their actual requirements, and record actionable blockers for unused nodes. Distinguish the whole resource pool from a per-service limit.

## Set up the team and assignments

The lead owns understanding the goal and constraints, conceiving the overall approach, decomposing and prioritizing tasks, integrating evidence, reflecting on hypotheses and results, adjusting direction, coordinating resources and staffing, acceptance, and user delivery. Distribute research, code analysis, implementation, deployment, measurement, and recording across the team. Participate in concrete execution when useful while maintaining the overall direction, assignments, and resource coordination.

Choose and reflect on optimization directions using the task goal and available evidence. The lead selects suitable methods and revisits the approach as new findings emerge.

At execution start, load the roles below into native workers. Keep role context across related assignments, while giving each assignment a concrete question and deliverable. Pass absolute paths to [the role contract](roles/common.md), the role file, task, applicable repository instructions, original evidence, and assigned output paths. Include the scope, deadline, authorized resources, dependencies, writer ownership, teammate addresses, and conditions for returning or stopping. Require workers to read those inputs themselves.

| Role instructions | Initial assignment and scaling | Record ownership |
| --- | --- | --- |
| [Direction and progress](roles/direction.md) | One advisor ranks directions, reflects on progress, and recommends a return to the main line. | Experiment overview: priorities, open questions, linked iterations, and the lead's decisions. |
| [Code and bottleneck analysis](roles/bottleneck.md) | At least one agent analyzes the system's end-to-end code path and measured bottlenecks. Prefer dedicated analysts for each active optimization direction, with several allowed on one direction. The lead chooses their number and scope. | Evidence and proposed measurements supplied to the assigned iteration writer. |
| [Experiment review and attribution](roles/experiment-review.md) | Independent reviewers assigned by direction and candidate; no self-review of an implemented candidate. | Assigned iteration notes, with execution analysis and independent review separately attributed. |
| [Knowledge research and exploration](roles/research.md) | Researchers assigned by direction and current bottleneck question. | Assigned research notes and reusable guidance. |
| [Experiment efficiency](roles/efficiency.md) | One supervisor covers continuous GPU collection and periodic analysis of experiments and useful agent parallelism, using native status and member progress updates. | Collector records and evidence supplied to the overview writer. |

Explicitly assign owners for implementation, integration, deployment, evaluation, and recording; these may be separate workers or compatible assignments on existing workers. Keep one owner per resource lifecycle and one writer per file or explicitly separated section.

Maintaining the number of actually working agents and their useful tasks is a standing lead objective during execution. Read the minimum and maximum from the task, rather than inventing counts. Analysts, researchers, reviewers, and execution workers count only while doing assigned work; direction and efficiency advisors are additional and excluded. Waiting, blocked, and completed workers do not count as active. Use native task state and messages to reconcile actual work on handoff and dependency changes; label unknown intervals rather than claiming exact activity or time-weighted averages without evidence. Respect harness limits, the task budget, and user stop instructions. If useful work cannot meet the requested count, report the real blocker instead of manufacturing activity. This objective ends on task termination or pause; completion is still judged by the optimization end conditions and required delivery.

When native shared Task tools are available, the lead creates work items and dependencies, assigning owners or authorizing self-claim of ready, unowned work within a stated scope and resource allocation. Workers may claim only within that authorization. Without Task tools, workers make directed requests and wait for explicit lead assignments; do not build a replacement queue, registry, or timer. Members may exchange evidence and challenge findings directly, keeping the lead informed of blockers and proposed priority or resource changes.

On restart, read existing experiment records, timing, resource/process ownership, and native task state. Check which workers actually exist; rebuild the team and reassign unfinished work when the harness has not restored them. Preserve the original budget and notes. Do not assume saved worker names represent live members.

## Work in parallel worktrees

Use independent Git worktrees for concurrent code changes and experimental candidates. A member may own a worktree, or a candidate group may share one with explicit file ownership. Read-only research and review can read the relevant worktree without creating another. The lead coordinates creation through native Git tools and records the agreed base, branch, absolute worktree path, responsible members, assigned resources, and result location in the existing experiment overview.

Give each member the paths for its actual checkout and evidence. Run edits, builds, deployment commands, and validation against that checkout. Give concurrent experiments distinct deployment identities, writable runtime caches, and result directories through the existing deployment mechanisms; reuse read-only model data where appropriate. Worktree isolation separates source changes, while the task's resource allocation determines how many experiments can run together. Take GPU counts and group counts from the task.

Before a measurement or review, identify the candidate's actual source and runtime configuration, including any uncommitted changes. Reviewers inspect that candidate rather than the lead's checkout. After deciding which changes to retain, assign integration into the agreed branch, resolve interactions, and validate the integrated result. Coordinate shared Git operations; each worktree has its own index, but branches and stashes belong to the same repository.

Remove an experimental worktree only after its changes and evidence have been retained or explicitly discarded and its members, builds, and services no longer use it. Preserve unfinished work on pause, and reuse or reassign the worktree deliberately on resumption.

## Advance each iteration

Every worker must actively send the lead results, evidence, the next useful action, and a request for a new assignment on completion or blockage, following the [role contract](roles/common.md). The lead responds with follow-up work or a reallocation, acknowledges an authorized self-claim, or states an explicit dependency wait, pause, or finish decision. Reuse worker context when available. Native notifications and messages advance coordination; neither a goal nor task status guarantees automatic self-claim, dependency wake-up, or immediate replacement of a finished worker.

1. Assign distinct code-analysis and research questions in parallel. Members send candidates directly to the direction advisor and relevant peers; the lead selects priorities from their evidence and assigns implementation and experiment owners.
2. As runs complete, executors send actual changes, commands, runtime identity, raw results, and their interpretation to the independent reviewer. The lead keeps unrelated work moving while review proceeds and bases acceptance on confirmed findings and necessary comparisons.
3. Reviewers share findings with the global analyst and researcher to reassess bottlenecks and applicability. The lead decides retain/refine/revert; an assigned worker performs the resulting edits or deployment. The reviewer records the decision, and the direction advisor updates the overview.
4. Request direction review on a contradicted hypothesis, important blocker, or costly side issue. Respond to actionable efficiency findings with an assignment or resource decision, and tell the relevant member what outcome to check.

Use the existing experiment and iteration records. Assigned writers incorporate peer evidence without concurrent overwrites; independent reviewers preserve the executor's interpretation and add their own attributed findings. Coordinate any lead contributions with the assigned writer. End each handoff with useful assigned work or a truthful wait/termination decision. Do not poll or keep agents busy merely to satisfy a count.

## Collect GPU usage

Run `scripts/gpu_usage.py` from this skill on each GPU host using Python 3.11+ and the installed `nvidia-smi` or `mx-smi`. It uses only the standard library; a host without a checkout needs only a copy of this script. Use the existing remote job manager or a task-owned persistent shell session so collection survives the supervisor's analysis and SSH disconnection.

From the checkout root on each host, set `GPU_RUN` to a new directory under the experiment's results, `GPU_INDICES` to that node's assigned host indices (comma-separated), and `DEADLINE` to the task's absolute ISO timestamp with UTC offset. Start once:

```bash
python3 -I .agents/skills/rsi/scripts/gpu_usage.py collect \
  --output "$GPU_RUN" --gpus "$GPU_INDICES" --deadline "$DEADLINE"
```

The collector prints its PID and output directory, then appends to `samples.jsonl` every 10 seconds. Use `--interval` to change the sampling interval. Backend detection selects the installed device tool; use `--backend nvidia` or `--backend metax` when both exist. Omit `--gpus` only when the task owns all visible GPUs, and omit `--deadline` only for a task without a time budget. Existing sample files are never overwritten; each resumed collection uses a new directory.

For periodic analysis, set `WINDOW_START` and `WINDOW_END` to the next completed window's ISO timestamps. Read the files on their host or through existing shared storage; the summary command may also read copies on the supervisor's machine. It does not start or interrupt collection:

```bash
python3 -I .agents/skills/rsi/scripts/gpu_usage.py summarize "$GPU_RUN" \
  --since "$WINDOW_START" --until "$WINDOW_END"
```

Pass additional run directories to summarize multiple nodes over the same window. The JSON includes per-GPU and per-node time-weighted utilization, sampling coverage, zero-utilization seconds, last sample times, and query errors. Each reading covers at most one sampling interval; uncovered time remains unknown. Check coverage and freshness alongside means. Zero utilization describes device activity, not whether an experiment should be running.

Request a stop on the collecting host:

```bash
python3 -I .agents/skills/rsi/scripts/gpu_usage.py stop "$GPU_RUN"
```

The stop marker, deadline, SIGINT, or SIGTERM ends collection after any in-flight query (bounded to 10 seconds). Confirm the final `end` record and process exit before releasing the collector. Keep its samples for the experiment report; on resumption start a new run directory. Do not signal a reused PID or stop shared monitoring.

## Pause or finish

A user pause or stop and the task deadline take precedence over queued messages, new-task requests, and staffing objectives. Stop assigning experiments, notify members, and have resource owners stop their processes and confirm exit; use native cancellation when needed. Preserve resumable work on pause. At completion, assign cleanup of resources with no remaining consumer after preserving required evidence.

Have the assigned writers complete delivery at the task's paths following the [experiment records guide](../../../rsi-playbooks/experiment-records.md). The lead accepts the delivery and summarizes retained changes, measured results, GPU sampling coverage, and unresolved blockers. Do not present role instructions or historical validation as evidence that the current team, experiments, or supervision actually ran.
