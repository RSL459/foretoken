# Benchmarks

English | [简体中文](README_zh.md)

`benchmarks/` is the evaluation module for Foretoken.

It can discover a Foretoken service from Kustomize or connect to an existing OpenAI-compatible endpoint. Use it to run repeatable latency and throughput experiments.

## When to Use It

- You want latency and throughput at a given concurrency or arrival rate.
- You want to compare concurrency, request count, generation settings, or server configs.
- You want a suitable load point or capacity plan under latency and throughput targets.

## Main Features

| Feature | Description |
|---|---|
| Performance benchmark | Send controlled load and measure latency, throughput, time to first token, and related metrics |
| Load sweep | Sweep concurrency, request count, or arrival rate to see how performance changes |
| Parameter sweep | Compare request and load configurations in batch |

## What It Produces

- Readable summary results in the console
- Locally saved configs, raw results, and metrics for later review
- Weights & Biases (W&B) experiment logs and charts when W&B is available

By default, the benchmark shows a console summary, saves local artifacts, and uploads to W&B. If W&B is unavailable, it warns and continues with local results. Use `--output local` to disable upload or add `quiet` to suppress console output. Local files are written under `--output-dir`.

## Examples

Benchmark a Foretoken Kubernetes deployment. The CLI reuses it when already present; otherwise it deploys the rendered resources and removes only those resources after the benchmark. When neither `--prompt` nor `--dataset` is specified, it uses a short built-in prompt:

```bash
foretoken bench examples/quickstart
```

Use the common sampling options directly and pass other OpenAI-compatible or backend-specific request fields through `--extra-body`:

```bash
foretoken bench examples/quickstart \
  --temperature 0 \
  --top-p 1 \
  --top-k 0 \
  --extra-body '{"seed":7,"min_tokens":8}'
```

Benchmark an existing endpoint with a fixed prompt:

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --prompt "hello" \
  --parallel 2 \
  --number 20
```

Local dataset file:

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset /path/to/conversation.jsonl \
  --parallel 4 \
  --number 20
```

Trace replay uses `--trace` for arrival timestamps and `--dataset` for payloads.
It accepts local JSONL, Hugging Face datasets, or `hf://` files and detects
StudyChat and Mooncake formats automatically.

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --trace KrisQ/StudyChat \
  --dataset KrisQ/StudyChat \
  --trace-start 600 \
  --trace-duration 300 \
  --trace-max-concurrency 32
```

The selected window is `[first + start, first + start + duration)`, with the
window start as replay time zero. `--trace-max-concurrency` limits active
requests, and time waiting for a concurrency slot is included in replay delay.
Mooncake can pair trace timing with randomly generated or dataset-backed request
content and can synthesize shared prefix blocks. See [trace examples and screenshots](docs/examples.md).

Random synthetic prompts (tokenizer required):

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --random-seed 0 \
  --min-prompt-length 128 --max-prompt-length 512 \
  --parallel 4 --number 20 --max-tokens 64 \
  --rate 5
```

Hugging Face dataset ID (rows: `messages`, `prompt`, or `user`[+`system`]):

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset r0b0tlab/qwen3.8-max-distillation-50k:train \
  --parallel 4 \
  --number 20
```

Multiple JSONL and Hugging Face sources can be comma-separated. `--number` is shared across all sources and divided in source order; earlier sources receive one extra request when needed. Sources run sequentially, then their results are merged. With W&B output, the experiment is one **group** and each dataset is one **run**:

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset /path/a.jsonl,org/name:train,/path/b.jsonl \
  --parallel 4 \
  --number 30
```

### Parameter sweep

When benchmarking a Foretoken Kustomize deployment, pass a JSONL file through `--bench-params` to compare request-execution configurations and load points. The run records every point and produces a Pareto chart of output tokens/s/user versus output tokens/s/GPU. See the [parameter sweep example](docs/examples.md#parameter-sweep).
