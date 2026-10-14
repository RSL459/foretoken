---
name: rsi
description: Execute, resume, pause, or finish an explicitly requested Foretoken RSI optimization task. Use only when the user asks to run RSI, not for ordinary coding or discussion of RSI designs.
---

<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Run an RSI task

English | [简体中文](SKILL_zh.md)

Choose collaboration and continuation tools that fit the task and the current harness. Use the same role responsibilities across environments; check which goal, delegation, messaging, task, and monitoring capabilities are available. Keep coordination work proportional to the experiment and make resource ownership, progress, and stopping conditions visible to the team.

## Establish the task

Read the repository instructions, the task supplied by the user, [shared workflow](../../../rsi-playbooks/README.md), [execution rules](../../../rsi-playbooks/tasks/README.md), and relevant prior experiment records. Members select references and prior findings from [shared guidance](../../../rsi-playbooks/guidance/README.md) for their current questions. Resolve these links from this skill directory. Keep task parameters in the task rather than copying defaults into this skill.

If the task supplies a starting configuration, check it against the task and current environment and treat it as an evolving starting point, not a fixed strategy. Otherwise, explore autonomously and record an initial configuration for comparison. In either case, carry forward applicable historical results, ruled-out directions, and unresolved questions. When current candidates are exhausted, revisit the direction and research new methods rather than automatically ending the task. Choose methods from the goal, evidence, and remaining budget; completion follows the task's end conditions.

Determine the requested action before starting anything. A pause, stop, or design discussion does not authorize starting or resuming experiments. For a new execution, record the task start and any deadline in its experiment notes. On resumption, read the existing timing and resource ownership first; preserve the agreed budget rather than resetting it.

Include every node listed in the task in the experiment plan. Check availability and existing owners, allocate independent candidates by their actual requirements, and record actionable blockers for unused nodes. Distinguish the whole resource pool from a per-service limit.

When using W&B, agree on readable tracking names before parallel runs. Use `--wandb-project` for an ongoing optimization topic, with a `foretoken-` prefix and a name identifying the model, hardware, and objective, such as `foretoken-qwen35-metax-inference`. Use one `--wandb-group` per RSI experiment, identified by its date or experiment name, to collect all iterations and parallel candidates. Use `--wandb-run-name` to distinguish the iteration, workload, concurrency, and repeat. All Workers in an experiment share its project and group. Resume with the same names; a new experiment for the same topic uses a new group in the existing project. Record names and run links in the experiment overview and iteration notes so Workers and the Recorder can find and compare results.

## Set up the team and assignments

The lead owns the goal and constraints, priorities, resources and staffing, cross-direction decisions, integration, acceptance, and final delivery. Workers own complete optimization questions, from research and design through implementation, deployment, measurement, and analysis. Advisors focus on independent research, bottleneck analysis, exploration, feedback, and reflection; the Recorder independently reviews candidate evidence and maintains experiment and decision history, evidence links, and the final report. The lead may also execute work while maintaining overall coordination.

The lead actively develops and revises optimization directions rather than only distributing an existing backlog. Connect members' local findings into a system-level understanding, consider alternative explanations, and decide where deeper investigation is worthwhile. Use Advisors' independent perspectives to challenge the current approach and keep useful questions moving without waiting for the user to supply the next idea. Methods and effort remain task-dependent.

At execution start, assign the roles below to team members. Give each Worker a self-contained research question with a clear expected outcome, not a sequence of separately approved commands. State the allowed changes, resources and handoff plan, remaining budget, completion conditions, collaborators, and evidence/output locations. Pass absolute paths to [the role contract](roles/common.md), role file, task, applicable repository instructions, and original evidence; members read these inputs themselves. Keep context across related assignments.

For example, assign a Worker to investigate queueing delay under the task's mixed-length workload: identify its cause, implement a suitable change if warranted, and compare the service against the retained approach without changing request acceptance or response semantics. Specify its checkout, service resources, budget, and Recorder. This authorizes investigation, candidate refinement, deployment, and measurement within those boundaries; it does not prescribe a particular algorithm or require a code change when the hypothesis is rejected.

| Role instructions | Initial assignment and scaling | Record ownership |
| --- | --- | --- |
| Lead | The lead develops and reflects on the approach, coordinates the team, and may execute work directly. | Decisions, acceptance, and user delivery; the Recorder records the decisions. |
| [Advisor](roles/advisor.md) | At least two members focus on complementary research questions, understand the code and system, explore community ideas, and provide bottleneck analysis, alternatives, feedback, and reflection. The lead sets staffing from useful perspectives, budget, and harness capacity. | Research findings and recommendations supplied to Workers, the lead, and the Recorder. |
| [Worker](roles/worker.md) | The main execution role owns a direction's code and bottleneck analysis, design, implementation, integration, deployment, measurement, and interpretation through to a conclusion. At least one Worker follows the system's end-to-end execution path. Prefer one or more dedicated Workers per active direction; the lead sets staffing from useful work and task resources, not GPU group counts. | Changes, raw evidence, and interpretation supplied to the Recorder and independent reviewer. |
| [Recorder](roles/recorder.md) | One by default, independently reviewing candidate behavior, comparison conditions, and attribution, and maintaining unified records and reusable findings with input from Advisors. Does not implement the candidates it reviews. | Experiment overview, iteration and decision history, evidence links, and final report. |
| [Monitor](roles/monitor.md) | One supervisor covers the whole team's work efficiency and resource utilization, including handoffs, duplicate work, blockers, useful parallelism, and continuous GPU collection. | Collector records and evidence supplied to the Recorder. |

Name members `<role>-<number-or-code>` in lowercase, using `lead`, `advisor`, `worker`, `recorder`, or `monitor` as the role prefix, for example `lead-01`, `advisor-01`, `worker-01`, `recorder-01`, `monitor-01`, or `worker-alpha`. Names identify members, not directions or tasks; reuse a member's name for follow-up assignments in the same role and keep names unique within the team. If the harness fixes the lead's messaging address, retain that actual address rather than assuming it can be renamed.

Split work where questions can advance independently. Closely coupled analysis, implementation, and experiments stay with one Worker or a cooperating group with a named integration owner. Research and review assignments can be narrower. Keep one owner per resource lifecycle and one writer per file or explicitly separated section.

Maintaining the number of actually working agents and their useful tasks is a standing lead objective during execution. Read the minimum and maximum from the task, rather than inventing counts. Count Workers, Advisors, and Recorders once per member, only while they are actually doing assigned work. Exclude the lead and Monitor, and do not count waiting, blocked, or completed members as working. Use native task state and messages to reconcile actual work on handoff and dependency changes; label unknown intervals rather than claiming exact activity or time-weighted averages without evidence. Respect harness limits, the task budget, and user stop instructions. If useful work cannot meet the requested count, report the real blocker instead of manufacturing activity. This objective ends on task termination or pause; completion is still judged by the optimization end conditions and required delivery.

Make assignments, dependencies, and resource reservations visible through the team's chosen coordination tools. Specify whether members may self-claim ready, unowned work. Plan resource handoffs with the affected owners so an already authorized successor can start when the current owner confirms release. Choose monitoring and follow-up arrangements that keep work moving through long commands and dependency changes.

On restart, read existing experiment records, timing, resource/process ownership, and native task state. Check which workers actually exist; rebuild the team and reassign unfinished work when the harness has not restored them. Preserve the original budget and notes. Do not assume saved worker names represent live members.

## Work in parallel worktrees

Use independent Git worktrees for concurrent code changes and experimental candidates. A member may own a worktree, or a candidate group may share one with explicit file ownership. Read-only research and review can read the relevant worktree without creating another. The lead coordinates creation through native Git tools and records the agreed base, branch, absolute worktree path, responsible members, assigned resources, and result location in the existing experiment overview.

Give each member the paths for its actual checkout and evidence. Run edits, builds, deployment commands, and validation against that checkout. Give concurrent experiments distinct deployment identities, writable runtime caches, and result directories through the existing deployment mechanisms; reuse read-only model data where appropriate. Worktree isolation separates source changes, while the task's resource allocation determines how many experiments can run together. Take GPU counts and group counts from the task.

Prepare a CLI supporting this deployment workflow and install or upgrade the shared source platform once before parallel candidate deployment, following the [source deployment guide](../../../docs/custom-deployment.md). Workers deploy from their own Foretoken worktree using a candidate-specific Kustomize namespace; `foretoken deploy` selects that checkout. When running elsewhere, pass `-e` with the candidate checkout and an absolute deployment path. Bind each candidate's own engine checkout with `--engine-source` when modifying engine code; later deployments reuse that worktree's recorded selection. The CLI isolates and reuses compilation caches by checkout. Coordinate shared controller, CRD, or platform changes through an explicit installation rather than reinstalling for each candidate.

Advance independent worktrees concurrently, overlapping research, implementation, builds, deployment, measurement, and review where resources allow. Keep active measurements' source and runtime unchanged. Reuse each candidate's environment for successive iterations, and let the existing deployment workflow reuse cached artifacts and prepare the required updates. Assign the next useful work as results arrive instead of waiting for every candidate to finish together.

Before a measurement or review, identify the candidate's actual source and runtime configuration, including any uncommitted changes. Reviewers inspect that candidate rather than the lead's checkout. After deciding which changes to retain, assign integration into the agreed branch, resolve interactions, and validate the integrated result. Coordinate shared Git operations; each worktree has its own index, but branches and stashes belong to the same repository.

Remove an experimental worktree only after its changes and evidence have been retained or explicitly discarded and its members, builds, and services no longer use it. Preserve unfinished work on pause, and reuse or reassign the worktree deliberately on resumption.

## Advance each iteration

The [Worker workflow](roles/worker.md) covers research, design, implementation, representative execution, measurement, and interpretation. Workers choose and refine approaches within their assignments without waiting for an Advisor proposal. The lead follows consequential findings and dependencies rather than approving each stage.

1. Advisors and Workers discuss mechanisms directly. Resolve questions that affect feasibility or whether a candidate executes early, using the actual service path. A disproved hypothesis can lead to another approach within the same assignment.
2. Run predetermined measurement groups continuously with existing benchmark tools where applicable. As evidence becomes available, the Recorder reviews the candidate and returns questions directly to its Worker. Review and recording overlap independent preparation; resource owners follow the agreed handoff plan when devices are no longer needed.
3. The lead combines reviewed findings across directions, chooses changes for the retained approach, and assigns integration and validation of the combined service. Workers carry out those assignments. The Recorder appends iteration conclusions, updates the overview, and maintains reusable guidance with Advisors.
4. Reconsider priorities when evidence changes the system-level understanding, a direction stalls, or preparation costs displace useful research. Use Advisors' and Monitor's findings to choose concrete changes of approach, staffing, or resource allocation.

Follow the [role contract](roles/common.md) for progress updates, decisions, and assignment completion. Continue authorized work after an intermediate result; when an assignment ends or cannot advance, the lead arranges follow-up work or an explicit wait, pause, or finish. On resumption, reconcile pending work with actual results and running processes before launching anything again.

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
