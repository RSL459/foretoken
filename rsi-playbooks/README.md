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
/goal Use the RSI skill and an Agent Team to complete the inference-system optimization in rsi-playbooks/tasks/qwen-decode.md and deliver its required results. Read the task, prior experiment records, and relevant guidance under rsi-playbooks/guidance/. As lead, develop the approach, delegate complete research questions with scope and resources for autonomous execution, integrate findings, and validate the combined approach, participating in execution when useful. Maintain the task's required number of actively working agents and respond to results and requests for new work. Follow the task's resources, time budget, and end conditions; on a user pause or stop, halt further work and arrange the necessary cleanup.
```

The lead uses one goal for the overall outcome and team progress, while members work within their roles. To pause, use `/goal clear` to end automatic continuation, then ask the team to stop this task's experiments and collectors.

### Codex

Open Codex in the repository and paste:

```text
/goal Use the RSI skill to complete the inference-system optimization in rsi-playbooks/tasks/qwen-decode.md and deliver its required results. Read the task, prior experiment records, and relevant guidance under rsi-playbooks/guidance/. As lead, develop the approach, delegate complete research questions with scope and resources for autonomous execution, integrate findings, and validate the combined approach, participating in execution when useful. Maintain the task's required number of actively working agents and respond to results and requests for new work. Follow the task's resources, time budget, and end conditions; on a user pause or stop, halt further work and arrange the necessary cleanup.
```

Codex uses its native `/goal` to maintain the task objective and its agent tools for delegation and follow-up. Use `/goal pause` to pause the goal and ask members to stop the task's experiments and collectors; use `/goal resume` to continue.

## Agent roles

Multiple Workers advance optimization directions in parallel, supported by the other roles. The lead sets staffing from task resources and parallelism requirements and retains member context for follow-up work:

| Role | Responsibility and staffing |
| --- | --- |
| Lead | Develops, reflects on, and chooses optimization directions; owns task breakdown, evidence synthesis, resource coordination, useful parallel work, and delivery, participating in execution when useful. |
| Think tank | At least two members with different focuses deliver independent research, alternatives, counterexamples, and cross-direction judgments, using original sources and upstream practice. The lead chooses their number within the budget and harness limits, and designates one member to maintain the overview. |
| Worker | Owns an optimization direction from code and bottleneck analysis through design, implementation, integration, deployment, measurement, and result analysis. At least one Worker follows the system's end-to-end execution path. Prefer one or more dedicated Workers per active direction; the lead determines total staffing. |
| Recorder | Independently reviews directions and candidates for benchmark shortcuts, comparison conditions, and the source of gains; owns iteration notes and captures reusable conclusions, applicability, and negative results in `guidance/`. Does not review its own implemented candidate. |
| Team efficiency | One supervisor covers the whole team's work efficiency and resource utilization. Periodically checks tasks, member progress, and useful parallelism, maintains continuous GPU collection, and follows up on delayed handoffs, duplicate work, blockers, or idle resources. |

Teammate names identify their role and scope, such as `worker-routing`, `recorder-throughput`, `thinktank-system`, and `thinktank-alternatives`. The [shared skill](../.agents/skills/rsi/SKILL.md#set-up-the-team-and-assignments) defines naming and assignment details.

Working-agent counts include Workers, think-tank members, and Recorders actually doing assigned work, counted once per member. Exclude the lead and efficiency supervisor; waiting, blocked, or completed members do not count as working. The lead arranges useful work within task and harness limits and addresses staffing shortfalls.

Assign each Worker a research question, scope, resources, budget, and expected outcome. Within that assignment, it owns research and design as well as execution, without waiting for a think-tank proposal or approval for each command or intermediate result. Think-tank members and Recorders collaborate directly with the Worker; review and recording overlap independent preparation. The lead handles changes of direction or shared resources, selects retained changes, and owns integrated validation and delivery.

Members report findings that affect others and request follow-up when their assignment is complete or cannot advance. One designated think-tank member owns the overview and Recorders own iteration notes, linking original evidence rather than duplicating it. On resumption, preserve the original budget, reconcile records with actual results and processes, and recreate missing members.

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

A research question may span several candidate iterations or conclude with evidence that an approach is unsuitable. An iteration evaluates one candidate; its workload groups and repeats belong together. Completion of the overall task follows its objectives, budget, and end conditions.

1. Define the behavior to improve, scope, and success criteria. Read relevant code, research, and prior results to identify a question worth investigating.
2. Develop a hypothesis and a comparison that can support or contradict it. Reuse comparable evidence; otherwise measure the reference approach. Resolve important feasibility questions before committing to a larger implementation.
3. Implement a viable candidate and use the [source deployment workflow](../docs/custom-deployment.md). Confirm the intended behavior through a representative execution before expanding measurements.
4. Run the selected [evaluations](../benchmarks/README.md). Use existing [sweeps](../benchmarks/docs/recipes.md) for predetermined workload groups where applicable, keeping comparison conditions stable. Analyze model outputs, logs, and profiles to explain differences.
5. Have an independent Recorder review the implementation and original results for behavior, comparison conditions, and attribution. Address questions while unrelated preparation continues, and preserve the evidence and conclusions in the [experiment records](experiment-records.md).
6. Refine or discard experimental candidates as evidence warrants. The lead selects reviewed changes for the retained approach and arranges combined service validation. Feed reusable findings into guidance and choose the next question within the remaining task budget.

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
