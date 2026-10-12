# Qwen Throughput and Decode Latency

English | [简体中文](qwen-decode_zh.md)

```text
Models: Qwen3.5-35B-A3B
Precision: fixed BF16
Deployment layout: unrestricted; examples include colocated serving and prefill/decode disaggregation
Per-service configuration: at most 8 GPUs per service; agent-selected GPU count within this limit, parallelism, CPU cores and memory
Available resources: 2×8 MetaX C500 GPUs, with 64 available CPU cores and 1 TiB memory per node
Minimum concurrently working subagents: 6
Maximum concurrently working subagents: 20
Minimum parallel experiments: 2
Maximum parallel experiments: have the agent determine the limit from available resources and per-experiment requirements, and record it in the experiment notes
Evaluation workloads: measure concurrency 1 and 16 separately per service, covering input/output lengths and natural answers; use foretoken perf for performance and foretoken perf --profile for bottleneck analysis
Accuracy evaluation: consider foretoken eval only when changes may affect accuracy; run it at most once per 20 completed performance iterations, not automatically every 20 iterations
Optimization objectives: improve single-request decode speed and total output throughput (tokens/s) at concurrency 16, and reduce decode latency (TPOT) in both groups
Allowed changes: unrestricted
Maximum time per experiment iteration: 10 minutes
Work duration: optimize autonomously for 12 hours from the start of task execution
Expected outcome / completion criteria: maximize throughput and minimize TPOT
Deliverables: for each iteration, list the changes, full foretoken perf commands, output throughput (tokens/s) and mean TPOT (ms/token) at concurrency 1 and 16; compare values and percentage changes against the initial approach and previous iteration under the same workload, with W&B links and plots; finish with the retained approach, its code/configuration, and measured results for each workload
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
  --max-concurrency 1 --num-prompts 16 --warmup-requests 4 \
  --random-seed 0 --temperature 0 --output experiment,raw,plot,wandb

# Required for the final retained approach; optional during iterations: natural answers.
foretoken perf path/to/qwen-deployment \
  --prompt "Explain the trade-offs between tensor parallelism and pipeline parallelism." \
  --max-concurrency 16 --num-prompts 16 --max-tokens 2048 \
  --warmup-requests 4 --temperature 0 --output experiment,raw,plot,wandb

# Optional: only for accuracy-affecting changes within the frequency limit above.
foretoken eval path/to/qwen-deployment \
  --tasks piqa,arc_easy,arc_challenge,hellaswag,winogrande \
  --num_fewshot 0 --limit 100 --output experiment,plot,wandb
```
