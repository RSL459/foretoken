<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Experiment recipes

English | [简体中文](recipes_zh.md) · [Evaluation and profiling](../README.md)

Choose a workload that answers the question under study. Run deployment examples from the repository root after [setup](../README.md#get-started); replace `examples/quickstart` with the model deployment being measured.

## Choose the comparison

| Question | Workload and result |
| --- | --- |
| How does concurrency affect capacity? | [Concurrency sweep](perf/sweep.md#compare-concurrency-settings): throughput versus latency |
| What load meets latency targets? | [Fixed-rate SLO measurement](perf/slo.md#measure-attainment-at-fixed-conversation-rates): attainment and goodput |
| How sensitive is capacity to the latency target? | [Threshold sweep](perf/sweep.md#compare-slo-thresholds-and-request-rates) |
| How does the service behave on real conversations? | [StudyChat data](perf/huggingface.md) or [ShareGPT](perf/sharegpt.md), with recorded or generated history |
| How does historical traffic affect queues and latency? | [StudyChat replay](perf/studychat.md): latency and replay delay |
| Does prefix reuse improve performance? | [Mooncake replay](perf/mooncake-trace.md), with and without shared prefixes |
| What changes after quantization? | [Method sweep](perf/sweep.md#compare-methods), [task scores](eval/README.md#compare-task-scores-across-deployments), and [probability differences](eval/distribution-comparison.md) |
| Where does execution spend time? | [Profiling](profile/README.md) |

## Long-context performance

Use the [long-context file](../scripts/common/long-context.jsonl) to vary input length at concurrency 1, reserving room for 512 output tokens. Copy it to `long-context.jsonl` and retain only rows within your model's context limit. The Quick Start allows 32,768 total tokens, so retain only the 16,384-token input row.

```bash
cp benchmarks/scripts/common/long-context.jsonl long-context.jsonl
```

After editing the copy:

```bash
foretoken perf examples/quickstart --dataset random \
  --sweep long-context.jsonl \
  --max-concurrency 1 --min-output-length 512 --max-output-length 512 \
  --num-prompts 4 --warmup-requests 1 --num-runs 1 --temperature 0 \
  --experiment-name long-context --output local,plot
```

Compare TTFT as context length grows, and TPOT for generation speed. Four requests per point provide an initial length comparison; use more requests and repetitions for tail latency measurements.

## Task accuracy and perplexity

These likelihood-based tasks require a [source-installed platform](../../docs/custom-deployment.md) or an existing Completions service returning input-token log probabilities. Run up to 100 samples per zero-shot task:

```bash
foretoken eval examples/quickstart \
  --tasks piqa,arc_easy,arc_challenge,hellaswag,winogrande \
  --num_fewshot 0 --limit 100 --output local,plot
```

Use [WikiText evaluation](eval/README.md#candidate-likelihood-and-perplexity) for perplexity. Task scores and perplexity answer different questions; compare each metric with the same task configuration and sample selection.

## Speculative decoding

Set `BASELINE` and `CANDIDATE` to deployment directories for the same target model, without and with speculative decoding:

```bash
BASELINE=path/to/non-speculative-deployment
CANDIDATE=path/to/speculative-deployment

foretoken perf "$BASELINE" "$CANDIDATE" --dataset random \
  --min-prompt-length 128 --max-prompt-length 256 \
  --sweep benchmarks/examples/sweep.jsonl --num-runs 3 --temperature 0 \
  --experiment-name speculative-decoding --output local,plot

foretoken eval "$CANDIDATE" --reference "$BASELINE" \
  --greedy-compare --context-length 512 --num-windows 8 --max-tokens 128 \
  --output local,plot
```

Compare serving speed and [greedy sequence agreement](eval/distribution-comparison.md#compare-greedy-generated-sequences). With Prometheus available, [speculative-decoding observations](../metrics.md#speculative-decoding-observations) help explain acceptance and stage costs.

## Cache, deployment, and scaling ablations

Set `BASELINE` and `CANDIDATE` to two deployments that differ in the mechanism under study:

```bash
BASELINE=path/to/baseline-deployment
CANDIDATE=path/to/ablation-deployment

foretoken perf "$BASELINE" "$CANDIDATE" \
  --trace valeriol29/mooncake-traces:conversation --dataset random \
  --trace-start 57s --trace-duration 8min --max-concurrency 16 \
  --trace-synthetic-prefix-reuse --random-seed 0 --max-tokens 64 \
  --slo-params '[{"ttft":"<=2s","tpot":"<=100ms"}]' --output local,plot
```

Compare latency, attainment, and goodput on the same replay. Kustomize results also show replica changes and [GPU allocation](../metrics.md#gpu-allocation). Apply changes to an existing deployment before running the comparison; benchmarks reuse it unchanged.

Redraw any retained experiment with `foretoken plot RESULT_DIR`, replacing `RESULT_DIR` with its printed path. See [sweep results](perf/sweep.md#read-results-and-redraw) to select metrics or change figure width.
