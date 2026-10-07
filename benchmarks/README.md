# Evaluation and profiling

English | [简体中文](README_zh.md)

Measure service latency and throughput with `foretoken perf`, score model answers with `foretoken eval`, and capture CPU/GPU execution to locate bottlenecks.

## Get started

Install Foretoken with Python 3.11 or later:

```bash
pip install foretoken
```

The deployment examples below run from the repository checkout prepared by the [Quick Start](../README.md#quick-start). A benchmark reuses an existing deployment unchanged, or deploys an absent one temporarily and removes the resources it created afterwards. A single-model deployment selects its model automatically; use `--model` for a multi-model deployment.

## Measure performance

```bash
foretoken perf examples/quickstart \
  --prompt "Explain what a token is in one sentence." \
  --max-concurrency 4 --num-prompts 20 --max-tokens 128 --output local
```

The summary reports successful and failed requests, response latency, and throughput. Streaming is enabled by default, so it also reports time to first token (TTFT) and time per output token (TPOT).

Choose realistic conversations, fixed token lengths, or recorded traffic in the [performance guide](docs/perf/README.md). Use [parameter sweeps](docs/perf/sweep.md) to compare load settings and deployments.

## Evaluate model quality

```bash
foretoken eval examples/quickstart --tasks gsm8k --limit 100 --output local
```

This scores 100 GSM8K math problems with lm-evaluation-harness, the default evaluator. The summary shows task scores and sample counts. See [quality evaluation](docs/eval/README.md) for other tasks, EvalScope, and resuming a run. To measure differences from a reference model, use [model comparison](docs/eval/distribution-comparison.md).

## Profile execution

The [profiling guide](docs/profile/README.md) shows how to capture a workload and open its timeline with `foretoken profile view`. It covers PyTorch Profiler, NVIDIA Nsight Systems, and MetaX mcTracer.

## Read and save results

Each local run prints its result directory under `results/`; `--output-dir` changes the parent directory. Performance runs save `metrics.json` for summaries and `raw_output.json` for individual requests. Quality runs retain evaluator reports in `native/`.

| Goal | Output option |
| --- | --- |
| Save locally | `--output local` |
| Save locally and compare in W&B | `--output local,wandb` (the default for `perf` and `eval`) |
| Also export PDF, SVG, PNG, and CSV figures | `--output local,wandb,plot` |
| Save without printing progress or summaries | `--output local,quiet` |

Run `wandb login` before using W&B. `quiet` saves logs in `run.log`; errors remain visible. Output selections can be combined, and `plot` retains the data needed to redraw figures.

To redraw a saved run, replace `RESULT_DIR` with the directory printed by the command:

```bash
foretoken plot RESULT_DIR --columns 2
```

See [performance charts](docs/perf/wandb.md), [metric definitions](metrics.md), or [quality scores](docs/eval/README.md#read-scores) to interpret results. [Experiment recipes](docs/recipes.md) cover capacity, quality, and deployment comparisons.
