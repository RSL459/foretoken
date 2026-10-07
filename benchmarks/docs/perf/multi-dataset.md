# Multiple datasets

English | [简体中文](multi-dataset_zh.md) · [Performance examples](README.md)

Mix conversation sources to measure a service under several kinds of traffic at once. After [setup](README.md#setup), separate selectors with commas:

```bash
foretoken perf examples/quickstart \
  --dataset r0b0tlab/qwen3.8-max-distillation-50k:train,ianncity/GLM-5.2-Conversation:train \
  --max-concurrency 4 --num-prompts 20 --output local
```

The datasets share one arrival rate, concurrency limit, and request budget. Local JSONL files or JSON conversation arrays can replace the remote selectors. Use random inputs as a separate workload.

## Set the traffic mix

`--num-prompts` is divided evenly by default. Add `--dataset-weights 3,1` to assign three quarters of the request budget to the first dataset and one quarter to the second. Each dataset stops when its turn budget is exhausted.

For a duration-bounded workload, replace `--num-prompts` with `--duration 5min`. Weights then control conversation sampling rather than fixed request shares.

A row can select a model and label its request class. For example:

```json
{"prompt":"Hello","model":"Qwen/Qwen3-0.6B","request_class":"interactive","output_length":32}
```

This selects the model, labels the request `interactive`, and targets 32 output tokens. Use different labels to compare interactive and batch traffic. [Conversation data](conversations.md#prepare-your-data) defines the input formats, per-row controls, and output-length rules.

## Compare traffic classes

Results include breakdowns by dataset, model, and request class, using the full experiment duration for each group's throughput and goodput. W&B displays their curves on the same elapsed-time axis and retains labels and output targets in the request table.

![P95 response latency by request class](../imgs/mixed-workload-wandb.png)

Use [SLO measurement](slo.md) to compare attainment across classes, or [parameter sweeps](sweep.md) to vary load settings.
