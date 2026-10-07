# Parameter sweeps

English | [简体中文](sweep_zh.md) · [Performance examples](README.md)

Measure the same workload at several load settings or on several deployments, then compare latency and throughput. Complete [setup](README.md#setup) and run from the repository root.

## Compare concurrency settings

```bash
foretoken perf examples/quickstart \
  --dataset random --min-prompt-length 128 --max-prompt-length 256 \
  --temperature 0 --sweep benchmarks/examples/sweep.jsonl \
  --warmup-requests 16 --num-runs 3 \
  --experiment-name concurrency --output local,wandb,plot
```

The [parameter file](../../examples/sweep.jsonl) measures concurrency 1, 2, and 4, with 384 requests and a fixed 256-token output at each point. Each point runs three times, with 16 warmup requests before each repetition. Sign in with `wandb login` first, or use `--output local,plot`.

Open `results/concurrency/sweep_summary.csv` and `plots/`. Compare throughput against latency under matching workload settings. Error bars show sample standard deviation across repetitions; percentiles are calculated per run before summarizing. `samples` and `failed_runs` identify incomplete points. Reusing an explicit `--experiment-name` replaces that experiment directory; omitting it creates a new timestamped directory.

## Define parameter combinations

A sweep file contains one JSON object per line. For example:

```json
{"max_concurrency":[1,2,4],"num_prompts":100,"min_output_length":128,"max_output_length":128}
```

Fields use CLI names with underscores. Lists are axes: several lists in one row expand into all combinations. Separate rows keep related settings together. A row's values override the command's settings; `_benchmark_name` optionally names the workload.

Compound values use another list level. For example, `"dataset": [["first.jsonl", "second.jsonl"]]` mixes both datasets at each point, rather than evaluating them separately. Time values with units are strings, such as `"duration": ["30s", "2min"]`.

Choose input and output lengths that fit the model's context. Fixed outputs require `min_tokens` and `ignore_eos`; see [random workloads](random.md).

## Choose a workload

| Parameter file | Comparison |
| --- | --- |
| [fixed-length](../../scripts/common/fixed-length.jsonl) | Concurrency across balanced, long-input, and long-output workloads |
| [fixed-arrival](../../scripts/common/fixed-arrival.jsonl) | Request rates with fixed short inputs and outputs |
| [fixed-capacity](../../scripts/common/fixed-capacity.jsonl) | Concurrency with long inputs and short outputs |
| [long-context](../../scripts/common/long-context.jsonl) | Input length; set output length and concurrency in the command |
| [conversation-rate](../../scripts/common/conversation-rate.jsonl) | Conversation starts/s for the selected dataset |
| [studychat-conversation](../../scripts/common/studychat-conversation.jsonl) | Concurrency for a StudyChat workload |
| [slo-thresholds](../../scripts/common/slo-thresholds.jsonl) | Latency thresholds and conversation start rates |
| [quantized-models](../../scripts/common/quantized-models.jsonl) | BF16 and 4-bit deployments across concurrency settings |

[Experiment recipes](../recipes.md) explain which comparison to choose. Edit length ranges to match the service before running large-context files.

## Compare SLO thresholds and request rates

Use the `slo-thresholds` file with a conversation dataset:

```bash
foretoken perf examples/quickstart \
  --dataset hf://datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/ShareGPT_V3_unfiltered_cleaned_split.json \
  --sweep benchmarks/scripts/common/slo-thresholds.jsonl \
  --temperature 0 --random-seed 0 --max-concurrency -1 \
  --num-prompts 100 --num-runs 1 --output local,plot
```

Compare attainment and goodput at each rate and threshold. The request budget counts HTTP turns, while the rate controls conversation starts. See [fixed-rate SLO measurement](slo.md#measure-attainment-at-fixed-conversation-rates) for the scoring rules.

A row's `"slo_params": [{"ttft": "<=250ms"}, {"ttft": "<=500ms"}]` scans two criteria choices. To run independent concurrency searches within one choice, add `--slo-search` and nest the objects: `"slo_params": [[{"p99_ttft": "<=250ms"}, {"p99_tpot": "<=100ms"}]]`. In a sweep, `--num-runs` repeats the complete search at each point rather than individual probes.

## Compare methods

```bash
foretoken perf examples/quantized-model/bf16 examples/quantized-model/bitsandbytes \
  --dataset random --min-prompt-length 128 --max-prompt-length 256 \
  --sweep benchmarks/examples/sweep.jsonl --num-runs 3 --output local,plot
```

Prepare model storage as described in the [quantized-model examples](../../../examples/quantized-model/README.md). All points for one method finish before the next starts. Existing deployments are reused unchanged; temporary deployments are removed between methods. Use `foretoken deploy` to apply configuration changes to an existing service before measuring it.

For existing services, `--url` accepts several URLs and `--model` accepts one shared model ID or one per URL. A sweep row can also select services with `"service": ["examples/quantized-model/bf16", "examples/quantized-model/bitsandbytes"]`. Named endpoint choices use `name`, `url`, and `model`, with optional `health_url`. Paths are relative to the command's working directory.

## Read results and redraw

```bash
foretoken plot results/concurrency --columns 2
```

This redraws the first example without sending requests. Repeat `--metric` or `--method` to select metrics or named methods; `--output-dir` saves an alternative layout separately. [Output settings](../../README.md#read-and-save-results) select result destinations. [Video workloads](video.md) use the same sweep workflow with their own generation parameters.
