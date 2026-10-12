# Qwen Throughput and Decode Latency

English | [简体中文](qwen-decode_zh.md)

```text
Models: Qwen3.5-35B-A3B
Optimization objectives: improve single-request decode speed and total output throughput (tokens/s) at concurrency 16, and reduce decode latency (TPOT) in both groups
Precision: fixed BF16
Deployment layout: unrestricted; examples include colocated serving and prefill/decode disaggregation
Per-service configuration: at most 8 GPUs per service; agent-selected GPU count within this limit, parallelism, CPU cores and memory
Available resources: 2×8 MetaX C500 GPUs, with 64 available CPU cores and 1 TiB memory per node
Minimum concurrently working subagents: 6
Maximum concurrently working subagents: 20
Minimum parallel experiments: 2
Maximum parallel experiments: have the agent determine the limit from available resources and per-experiment requirements, and record it in the experiment notes
Parallel scheduling: reduce idle resources through useful parallel investigation, implementation, and experiments
Evaluation workloads: measure concurrency 1 and 16 separately per service using random-length workloads and StudyChat conversations; see the full commands under "Evaluation commands" below
Accuracy evaluation: consider foretoken eval only when changes may affect accuracy; run it at most once per 20 completed performance iterations, not automatically every 20 iterations
Allowed changes: source code, configuration, and other implementation artifacts may be changed within the precision and resource constraints above. Optimization directions include, but are not limited to, deployment configuration, concurrency and batching, parallelism, prefill/decode disaggregation, inference engines and scheduling, kernel optimization and fusion, compilation and graph execution, communication, memory management, KV caching and offloading, speculative decoding, sampling, routing and load balancing, admission and queueing, autoscaling, and CPU/I/O optimization
Iteration definition: one candidate change from deployment through the required performance comparisons, analysis, and a retain/revert decision counts as one iteration; measurements at concurrency 1 and 16 belong to the same iteration
Measurement budget per iteration: 10 minutes by default to keep iterations fast, covering that iteration's perf/eval measurements only, excluding investigation, implementation, compilation, deployment, and result analysis. If the budget or request count does not suit the actual workload, the agent may adjust it while keeping comparisons valid and recording the reason and actual time spent
Work duration: optimize autonomously for 12 hours from the start of task execution
Expected outcome / completion criteria: no fixed metric thresholds; continue maximizing throughput and minimizing TPOT until the time budget expires or the user explicitly asks to stop. When a direction yields no gains, continue diagnosis, online research, and alternative approaches rather than ending early based on a subjective judgment that no optimization opportunities remain
Deliverables (<iteration> is the approach name passed to --iteration):
  - Changes and commands: record each iteration's code/configuration changes and full foretoken perf commands in the "Changes and commands" section of results/qwen-decode/iterations/<iteration>/notes/iteration.md.
  - Performance metrics: record output throughput (tokens/s) and mean TPOT (ms/token) at concurrency 1 and 16 for each workload in the "Performance metrics" table in the same iteration.md.
  - Comparative analysis: record values and percentage changes against the initial approach and previous iteration under the same workload, with explanations, in the "Comparative analysis" section of the same iteration.md.
  - Evidence: record W&B links, plots, and raw result paths in the "Evidence" section of the same iteration.md; retain automatically saved run artifacts under results/qwen-decode/iterations/<iteration>/runs/.
  - Execution efficiency: record the time-weighted mean active subagent count over the full interval from task start to finish (excluding idle or waiting agents), mean GPU/CPU utilization, and mean memory occupancy in the "Execution efficiency" section of results/qwen-decode/notes/experiment.md. State the observation interval, resource scope, sampling coverage, and reasons for low utilization, with references to raw records.
  - Final approach: record the retained approach, its code/configuration, per-workload measurements, and an iteration comparison summary in results/qwen-decode/notes/experiment.md.
  - User-facing summary: create rsi-playbooks/tasks/qwen-decode/<experiment>/ using the experiment name. Summarize the conclusions, iteration comparisons, execution efficiency, and W&B links from experiment.md in that directory's report.md; place key plots in figures/ and reference them with relative paths. Deliver the summary file path.
```

See [optimization tasks](README.md#autonomous-execution) for execution and resource scheduling, and the [experiment records guide](../experiment-records.md) for recording results.

## Evaluation commands

Run from the repository root, replacing the deployment directory and W&B API key placeholders. Results are saved under `results/qwen-decode/` on the execution machine. Use `baseline` for the initial approach, rename it for a new approach, and reuse it for repeat measurements of the same approach. The agent writes the notes above; commands generate metrics and plots.

Run the random workload once with `--max-concurrency 1` and again with `16`; keep request, warmup, and evaluation samples identical between the two runs. The StudyChat command is required for the final retained approach and is otherwise optional. See [recipes](../../benchmarks/docs/recipes.md) for more workloads.

```bash
export WANDB_API_KEY="<your-wandb-api-key>"

# Every performance iteration: vary input and output lengths.
foretoken perf path/to/qwen-deployment --dataset random \
  --min-prompt-length 128 --max-prompt-length 4096 \
  --min-output-length 128 --max-output-length 512 \
  --max-concurrency 16 --num-prompts 160 --warmup-requests 4 \
  --random-seed 0 --temperature 0 --output experiment,raw,plot,wandb \
  --output-dir results/qwen-decode --iteration baseline

# Required for the final retained approach; optional during iterations: StudyChat conversations.
foretoken perf path/to/qwen-deployment \
  --dataset hf://datasets/KrisQ/StudyChat/data.jsonl \
  --max-concurrency 16 --num-prompts 128 --max-tokens 2048 \
  --warmup-requests 4 --temperature 0 --output experiment,raw,plot,wandb \
  --output-dir results/qwen-decode --iteration baseline

# Optional: only for accuracy-affecting changes within the frequency limit above.
foretoken eval path/to/qwen-deployment \
  --tasks gsm8k --num_fewshot 0 --limit 20 --output experiment,plot,wandb \
  --output-dir results/qwen-decode --iteration baseline
```
