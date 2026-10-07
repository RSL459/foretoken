# Compare performance in W&B

English | [简体中文](wandb_zh.md) · [Performance examples](README.md)

Use W&B to compare runs and inspect changes over time. Run `wandb login` once, then choose a project and group:

```bash
foretoken perf examples/quickstart \
  --num-prompts 20 --max-tokens 128 --output local,wandb \
  --wandb-project foretoken-bench --wandb-group qwen-comparison \
  --wandb-run-name quickstart
```

`--wandb-entity` selects the account or team. Runs with the same group can be compared in its Workspace. Sweeps and multi-dataset runs generate a group when none is supplied; single runs are ungrouped by default. Child labels are appended to the chosen run-name prefix.

## Choose a view

| View | What to inspect |
| --- | --- |
| Time | Throughput, concurrency, failures, and latency percentiles over one-second completion windows |
| Cumulative | Throughput averaged over elapsed time |
| Request index | Individual timings, token counts, and output targets in send order |
| Summary | Final aggregate values, including P50/P95/P99 |
| Warmup | Warmup curves and comparison with measurement, when enabled |

Warmup is excluded from formal metrics. Mixed workloads add dataset, model, and request-class breakdowns on a shared time axis, with labels retained in the request table. [Metric definitions](../../metrics.md#curves) explain windows and units.

![Timings and token counts in request order](../imgs/request-order-wandb.png)

## Compare deployments

Kustomize runs also show replica changes and GPU allocation. GPU-seconds and GPU-hours are reported by device resource name when observations cover the whole run; partial coverage is shown separately. See [GPU allocation](../../metrics.md#gpu-allocation).

With Prometheus available, speculative-decoding runs include [acceptance and stage-time observations](../../metrics.md#speculative-decoding-observations). A sweep's comparison run summarizes measurements across parameter points and repetitions.

Use [output settings](../../README.md#read-and-save-results) to retain local files or export figures alongside W&B. A W&B publication failure returns a command error and retains already-produced artifacts.
