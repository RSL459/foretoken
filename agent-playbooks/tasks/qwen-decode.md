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
Evaluation workloads: measure concurrency 1 and 16 separately per service using random-length workloads and StudyChat conversations; see the full commands under "Evaluation commands" below
Accuracy evaluation: consider foretoken eval only when changes may affect accuracy; run it at most once per 20 completed performance iterations, not automatically every 20 iterations
Allowed changes: unrestricted within the precision and resource constraints above, including deployment configuration, concurrency and batching, parallelism, prefill/decode disaggregation, inference engines and scheduling, kernel optimization and fusion, compilation and graph execution, communication, memory management, KV caching and offloading, speculative decoding, sampling, routing and load balancing, admission and queueing, autoscaling, and CPU/I/O optimization
Maximum time per experiment iteration: 10 minutes
Work duration: optimize autonomously for up to 12 hours from the start of task execution
Expected outcome / completion criteria: no fixed metric thresholds; continue maximizing throughput and minimizing TPOT until no further optimization opportunities remain or the time budget expires
Deliverables:
  - Changes and commands: code/configuration changes and full foretoken perf commands for each iteration.
  - Performance metrics: output throughput (tokens/s) and mean TPOT (ms/token) at concurrency 1 and 16 for each workload and iteration.
  - Comparative analysis: values and percentage changes against the initial approach and previous iteration under the same workload, with an explanation of the differences.
  - Evidence: W&B links, plots, and raw result paths for each iteration.
  - Final approach: the retained approach, its code/configuration, and measured results for each workload.
```

See [optimization tasks](README.md#autonomous-execution) for execution and resource scheduling, and the [experiment records guide](../experiment-records.md) for recording results.

## Evaluation commands

Run from the repository root, replacing the deployment directory and W&B API key placeholders. Run the first two commands with `--max-concurrency 1` and `16`. Size request, warmup, and evaluation samples to fit the iteration budget, keeping reference and candidate settings identical. See [recipes](../../benchmarks/docs/recipes.md) for more workloads.

```bash
export WANDB_API_KEY="<your-wandb-api-key>"

# Every performance iteration: vary input and output lengths.
foretoken perf path/to/qwen-deployment --dataset random \
  --min-prompt-length 128 --max-prompt-length 4096 \
  --min-output-length 128 --max-output-length 512 \
  --max-concurrency 16 --num-prompts 160 --warmup-requests 4 \
  --random-seed 0 --temperature 0 --output experiment,raw,plot,wandb

# Required for the final retained approach; optional during iterations: StudyChat conversations.
foretoken perf path/to/qwen-deployment \
  --dataset hf://datasets/KrisQ/StudyChat/data.jsonl \
  --max-concurrency 16 --num-prompts 128 --max-tokens 2048 \
  --warmup-requests 4 --temperature 0 --output experiment,raw,plot,wandb

# Optional: only for accuracy-affecting changes within the frequency limit above.
foretoken eval path/to/qwen-deployment \
  --tasks gsm8k --num_fewshot 0 --limit 20 --output experiment,plot,wandb
```
