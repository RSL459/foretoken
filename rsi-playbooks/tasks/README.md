# Optimization Tasks

English | [简体中文](README_zh.md)

These tasks define goals, scope, constraints, and deliverables. Use the [task template](../templates/task-template.md) to specify the model, resources, workloads, and objectives; the agent follows the [shared workflow](../README.md#steps) for analysis, design, implementation, evaluation, and recording.

## Autonomous execution

Continue working within the task scope and resource budget. Judge completion by the objective and measured results.

- When earlier experiments exist, read their records, check the conditions, and continue from retained approaches, ruled-out directions and unresolved questions. Reuse comparable results and spend resources on new questions; if changed conditions or insufficient evidence call for a repeat, state what it should establish.
- Make the build, deployment, measurement, recording and comparison workflow usable with existing tools. Address recurring delays or tooling gaps at their owning entrypoints so the improvement shortens subsequent experiment cycles.
- Carry investigation, design, implementation, deployment, evaluation, and analysis through to completion. During investigation, consult relevant papers, official documentation, and upstream practices online, and develop an approach grounded in the current implementation. Resolve problems that can be handled independently and proceed with established next steps.
- Use evidence to choose the next action after each iteration. Investigate ineffective approaches, refine or replace them, and assess the remaining gap to the objective after a partial improvement.
- Include every node listed in the task in resource planning. Check available GPUs, CPU cores, and memory on each node, then allocate independent candidates according to their requirements. Track experiment progress and GPU utilization across all nodes, and schedule experiments when resources and candidates are available. Record why any node is unused and resolve actionable blockers. Coordinate shared resources to keep results comparable.
- Maintain useful work within the task's parallelism requirements throughout execution. Process subagent results and assign follow-up work as agents finish; schedule the next candidate as experiments finish. Advance independent investigation and implementation while measurements run, and reassign work when blocked. Count subagents as active while they are executing tasks.
- Keep iterations short, using enough requests or measurement time to judge the current hypothesis. Increase samples, repeat measurements or extend a run when gains are uncertain or tail latency or stability needs closer evaluation, and state the purpose. The total work period includes analysis, implementation and deployment; it is not a continuous load-test duration.
- Treat code changes, service startup, and individual test runs as progress rather than task completion. Support conclusions with measurements under actual workloads; evaluate answer quality when changes affect generation behavior.
- Keep experiment records current. At completion, state which objectives were met, which changes were retained, and where results are stored. If the budget is exhausted or progress requires outside intervention, identify the concrete blocker and what is needed to resume.

Reference task: [Qwen throughput and decode latency](qwen-decode.md).
