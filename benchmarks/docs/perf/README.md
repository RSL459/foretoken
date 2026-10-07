# Measure serving performance

English | [简体中文](README_zh.md) · [Evaluation and profiling](../../README.md)

Use `foretoken perf` to measure response latency and throughput under the load your service will receive.

## Setup

Complete the [shared setup](../../README.md#get-started) and run deployment examples from the repository root. Start with 20 requests at concurrency 4:

```bash
foretoken perf examples/quickstart --num-prompts 20 --max-concurrency 4 \
  --max-tokens 128 --output local
```

This uses the built-in `Hello` prompt. The summary reports request success, latency, TTFT, TPOT, and throughput; local results are saved in the printed directory. The default load has one concurrent request and no arrival-rate limit. Streaming is enabled.

## Choose a workload

| What to measure | Guide |
| --- | --- |
| A repeated prompt | [Fixed prompts](fixed-prompt.md) |
| Controlled input/output token lengths | [Random workloads](random.md) |
| Real conversation history | [Local conversations](conversations.md), [Hugging Face](huggingface.md), [ShareGPT](sharegpt.md) |
| Tool-calling requests | [Tool data](tools.md) |
| A traffic mix across datasets or models | [Multiple datasets](multi-dataset.md) |
| Recorded arrival times | [StudyChat](studychat.md), [Mooncake traces](mooncake-trace.md) |
| Complete, non-streamed responses | [Non-streaming requests](non-streaming.md) |
| Video generation | [Video workloads](video.md) |

Use [arrival rate and concurrency](arrival-rate.md) to control load, [parameter sweeps](sweep.md) to compare settings or deployments, and [SLO measurement](slo.md) to find load levels meeting latency targets.

## Use an existing endpoint

Replace the URL and model below with your service's Chat Completions endpoint and served model ID:

```bash
foretoken perf --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen/Qwen3-0.6B --prompt Hello \
  --num-prompts 20 --max-tokens 128 --output local
```

This does not use Kubernetes. Add `--api-key` for authentication. For a Foretoken Gateway deployment, pass its Kustomize directory to discover the routing address and headers automatically.

## Read results

Start with success rate, then compare latency percentiles and throughput under the same workload. [Performance metrics](../../metrics.md) defines their units and statistical scope. [W&B charts](wandb.md) show how performance changes over time and across individual requests; [output settings](../../README.md#read-and-save-results) also support local figures.

All options are listed by `foretoken perf --help`. To explain an execution bottleneck, [capture a profile](../profile/README.md) in a separate run.
