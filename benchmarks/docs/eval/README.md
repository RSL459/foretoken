<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Evaluate model quality

English | [简体中文](README_zh.md) · [Evaluation and profiling](../../README.md)

Score model answers with lm-evaluation-harness or EvalScope. After [setup](../../README.md#get-started), run 100 GSM8K math problems from the repository root:

```bash
foretoken eval examples/quickstart --tasks gsm8k --limit 100 --output local
```

lm-evaluation-harness (`lm-eval`) is the default evaluator. Omit `--limit` to run the complete task.

## Read scores

The summary lists task scores, answer filters, sample counts, and available standard errors. A filter describes how the framework extracts an answer for scoring. Compare the same metric and filter with matching task settings and sample selection.

Open the result directory printed by the command:

| File or directory | Contents |
| --- | --- |
| `metrics.json` | Scores, subsets, filters, sample counts, and available uncertainty or execution status |
| `native/` | Evaluator reports and generated sample records |
| `evaluator.log` | Evaluator progress and diagnostics |

Add `--log_samples` for individual lm-eval inputs and answers. [Output settings](../../README.md#read-and-save-results) enable W&B and figures; W&B's `Evaluation/Scores` table retains the detailed scores.

## Choose lm-evaluation-harness tasks

Task names and options follow the [upstream interface](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md). Use comma-separated `--tasks` for several tasks, `--num_fewshot 0` for zero-shot prompts, and `--model_args num_concurrent=4` for four concurrent API requests. Prompting and scoring come from the chosen task.

### Candidate likelihood and perplexity

PIQA selects answers by comparing their probabilities. WikiText measures perplexity: lower values mean the model predicts the text more readily. These tasks need a [source-installed Foretoken platform](../../../docs/custom-deployment.md) or an existing Completions service returning input-token log probabilities:

```bash
foretoken eval examples/quickstart --tasks piqa --limit 100 --output local

foretoken eval examples/quickstart --tasks wikitext --limit 100 --output local
```

The tokenizer is inferred from the deployment, or from `--model` for a URL. Override it with `--model_args tokenizer=MODEL_OR_LOCAL_DIRECTORY` for a serving alias or client-local tokenizer files. Candidate scoring uses raw text by default; add `--apply_chat_template` when the task requires an instruction-model template. Perplexity uses the original corpus without a chat template.

## Use EvalScope

```bash
foretoken eval examples/quickstart --evaluator evalscope \
  --datasets gsm8k --limit 100 --output local
```

Saved reports include category and subset scores. Configure tasks with [EvalScope's native options](https://evalscope.readthedocs.io/en/latest/get_started/basic_usage.html), such as `--dataset-args` and `--generation-config`.

The installed options are listed by `foretoken eval --evaluator lm-eval --help` and `foretoken eval --evaluator evalscope --help`.

## Compare task scores across deployments

Prepare the [quantized-model examples](../../../examples/quantized-model/README.md), then pass the deployment directories before the task options:

```bash
foretoken eval examples/quantized-model/bf16 examples/quantized-model/bitsandbytes \
  --tasks piqa --limit 100 --output local,plot
```

The deployments run in turn. `evaluation_comparison.csv` aligns task scores and available standard errors; each run retains its evaluator reports. To compare probability distributions or generated token sequences instead of task scores, use [reference/candidate comparison](distribution-comparison.md).

## Use an existing endpoint

Replace the URL and model below with your service's Chat Completions endpoint and served model ID:

```bash
foretoken eval --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen/Qwen3-0.6B --tasks gsm8k --limit 100 --output local
```

This uses no Kubernetes resources. Add `--api-key` for authentication. For Foretoken Gateway access, pass the Kustomize directory to discover routing automatically.

## Resume an evaluation

Keep local output for a single-deployment evaluation. After an interruption, repeat the original command with `--resume` pointing to its printed result directory; replace `results/previous-run` below:

```bash
foretoken eval examples/quickstart --tasks gsm8k --limit 100 \
  --resume results/previous-run --output local
```

The command reuses completed generations or likelihood-scoring windows for lm-eval, and completed predictions and reviews for EvalScope. It writes combined results into a new directory, leaving the original unchanged. Resume from the newest directory after another interruption, keeping weights, task settings, and sample selection unchanged; EvalScope also requires the same service URL. Use `--resume` rather than native `--use_cache` or `--use-cache` for this workflow.

[Distribution comparisons](distribution-comparison.md#resume-a-distribution-comparison) can also resume completed scoring windows.
