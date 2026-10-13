# RSI Playbooks

English | [简体中文](README_zh.md)

Foretoken is an inference infrastructure framework designed for RSI (Recursive Self-Improvement), enabling agents to autonomously modify, deploy, evaluate, and optimize inference systems.

These playbooks provide task guidance, experimental methods, and reusable knowledge. Validated findings are incorporated to make subsequent optimization work more effective.

## Start an optimization task

Clone the repository:

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
```

### Claude Code

Start a dedicated interactive session from this directory:

```bash
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude
```

This enables Agent Teams for this session. Paste the following into that session, or one with Teams already enabled. Replace the file path to use your own task:

```text
/goal Use the RSI skill and an Agent Team to complete the inference-system optimization in rsi-playbooks/tasks/qwen-decode.md and deliver its required results. Read the task, prior experiment records, and relevant guidance under rsi-playbooks/guidance/. As lead, develop the approach, break down tasks, reflect on findings, and keep the team moving, participating in execution when useful. Maintain the task's required number of actively working agents and respond to results and requests for new work. Follow the task's resources, time budget, and end conditions; on a user pause or stop, halt further work and arrange the necessary cleanup.
```

The lead uses one goal for the overall outcome and team progress, while members work within their roles. To pause, use `/goal clear` to end automatic continuation, then ask the team to stop this task's experiments and collectors.

### Codex

Open Codex in the repository and paste:

```text
Use the RSI skill to complete the inference-system optimization in rsi-playbooks/tasks/qwen-decode.md and deliver its required results. Read the task, prior experiment records, and relevant guidance under rsi-playbooks/guidance/. As lead, develop the approach, break down tasks, reflect on findings, and coordinate native agents, participating in execution when useful. Maintain the task's required number of actively working agents and respond to results and requests for new work. Follow the task's resources, time budget, and end conditions; on a user pause or stop, halt further work and arrange the necessary cleanup.
```

Codex uses the same roles through the native delegation, messaging, and follow-up tools available in the session, not Claude's Agent Team or `/goal`.

## Agent roles

Multiple Workers advance optimization directions in parallel, supported by the other roles. The lead sets staffing from task resources and parallelism requirements and retains member context for follow-up work:

| Role | Responsibility and staffing |
| --- | --- |
| Lead | Develops, reflects on, and chooses optimization directions; owns task breakdown, evidence synthesis, resource coordination, useful parallel work, and delivery, participating in execution when useful. |
| Direction and progress | One advisor independently examines assumptions, methods, and progress, connects findings across directions, proactively recommends questions to investigate and changes of approach, and writes the experiment overview. |
| Worker | Owns an optimization direction from code and bottleneck analysis through design, implementation, integration, deployment, measurement, and result analysis. At least one Worker follows the system's end-to-end execution path. Prefer one or more dedicated Workers per active direction; the lead determines total staffing. |
| Recorder | Independently reviews directions and candidates for benchmark shortcuts, comparison conditions, and the source of gains; owns iteration notes and captures reusable conclusions, applicability, and negative results in `guidance/`. Does not review its own implemented candidate. |
| Knowledge research and exploration | Researchers by direction examine original sources and upstream practice, proposing applicable methods and recording findings. |
| Team efficiency | One supervisor covers the whole team's work efficiency and resource utilization. Periodically checks tasks, member progress, and useful parallelism, maintains continuous GPU collection, and follows up on delayed handoffs, duplicate work, blockers, or idle resources. |

Working-agent counts include Workers, researchers, and Recorders while they are doing assigned work. Direction and efficiency advisors are additional. The lead arranges useful work within task and harness limits and addresses staffing shortfalls.

Workers and researchers discuss methods directly. Workers send changes, raw results, and interpretation to Recorders, who return review findings and requests for missing evidence to Workers. The lead coordinates key trade-offs, priorities, and resources. Members request new work on completion or blockage; the lead assigns follow-up work or adjusts responsibilities. Where shared task tools are available, members may also claim ready work within their authorization. The direction advisor owns the overview, Recorders own assigned iteration notes, and the lead accepts their outputs. On resumption, preserve the original budget and records and recreate missing members.

### Parallel workspaces

Use independent Git worktrees (separate working directories of the same repository) for concurrent changes and experiments, organized by member or experiment group. The lead coordinates the base revision, owners, resources, and result locations. Each group edits, builds, deploys, and measures from its own checkout, using distinct deployment identities, writable caches, and result directories. Read-only research and review can read the relevant checkout directly.

Experiment counts and GPU allocations come from the task. Reviewers examine each candidate's actual code and results; after selecting retained changes, the lead arranges integration and validation. Remove worktrees once changes and evidence are preserved and their users have finished.

## Design goals

- Rapid deployment: apply code changes quickly to inference services in the target cluster.
- Testing and feedback: measure performance, model quality, and resource costs to evaluate the effects of a change.
- Observation and diagnosis: use logs, metrics, and profiling to locate runtime problems and performance bottlenecks.
- Experiment records: connect each iteration's changes, configurations, results, and decisions for comparison and reproduction.
- References and shared experience: find and update references, and turn experimental findings into reusable guidance.
- Behavior and attribution checks: examine actual model behavior, identify metric gaming, and determine whether gains come from the intended change.

## Steps

An iteration covers one candidate change, from deployment through the required performance comparisons and result analysis to a decision to retain or revert it. Measurements of that candidate across workloads and concurrency levels belong to the same iteration.

1. Define the behavior to improve and how to judge success, such as reducing time to first token under a given workload while preserving answer quality.
2. Set the scope: focus on routing, the inference engine, or another specific area, or leave it open to changes across the whole system.
3. Read the code and relevant research and practice. Use existing measurements to understand the system's current behavior, taking additional measurements as needed.
4. Analyze the causes and opportunities for improvement, develop your own hypotheses, and design an approach. State the expected effects and choose workloads and metrics that test those hypotheses. If comparable results are unavailable, measure the service before making the change.
5. Change the code or configuration and update the inference service through the [source deployment workflow](../docs/custom-deployment.md).
6. Run the selected [evaluations](../benchmarks/README.md) and compare results before and after the change. Use model outputs, logs, and profiling to determine what accounts for the differences.
7. Have an independent reviewer examine the implementation and raw results for benchmark shortcuts, changed model behavior, and comparison conditions, assessing attribution and any needed follow-up measurements.
8. Record each run, its interpretation, and review findings following the [experiment records guide](experiment-records.md).
9. Keep, refine, or revert the change, then choose the next question to investigate. Add reusable findings to the guidance and references.

## Choose evaluations

Select evaluations for the current optimization goal. See the [experiment records guide](experiment-records.md) for commands and recording options.

| Evaluation goal | Tools and commands | Results to inspect |
| --- | --- | --- |
| Compare latency, decode speed, and throughput | [Performance evaluation](../benchmarks/docs/perf/README.md), `foretoken perf` | Success count, latency distribution, TPOT, throughput, and actual output length |
| Evaluate answer quality | [Quality evaluation](../benchmarks/docs/eval/README.md), `foretoken eval` | Scores, sample counts, scoring method, and individual answers |
| Locate computation, communication, and waiting costs | [Profiling](../benchmarks/docs/profile/README.md), `foretoken perf --profile` | Execution timeline; use separate unprofiled runs for speed comparisons |
| Compare concurrency, input lengths, and traffic patterns | [Sweep and workload configurations](../benchmarks/docs/recipes.md) | Metrics and trends across workload points |

Inspect command options with `foretoken perf --help` and `foretoken eval --help`.

## Task entry points

Choose a task from [optimization tasks](tasks/README.md), and consult [shared guidance](guidance/README.md) for references and prior findings.
