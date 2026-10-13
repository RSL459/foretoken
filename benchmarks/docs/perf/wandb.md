# W&B output

English | [简体中文](wandb_zh.md) · [Performance examples](README.md)

After [setup](README.md#setup), choose the project, group, and run name:

```bash
foretoken perf examples/quickstart \
  --num-prompts 20 --output local,wandb \
  --wandb-project foretoken-bench \
  --wandb-group qwen-comparison \
  --wandb-run-name quickstart
```

Open the run link printed by the command; it also appears in quiet mode. Use `--wandb-entity` to select an account or team. Set the same `--wandb-group` for runs you want to compare in a group's Workspace. Sweeps and multi-dataset runs generate a group when none is supplied; single runs are ungrouped by default.

## Follow progress and compare results

During HTTP measurement, cumulative completion counts, failures, mean latencies, and throughput are recorded once per second and uploaded during the run. These curves describe completed requests; throughput uses elapsed measurement time. When measurement finishes, the page also shows final metrics, P50/P95/P99 values, completion-window curves, and per-request series. Summary retains the final values.

![Per-request timings and token counts](../imgs/request-order-wandb.png)

Mixed workloads include breakdowns by dataset, model, and request class. Kustomize runs add replica and GPU-allocation observations; services with Prometheus can also report resource usage and speculative decoding. See [Performance metrics](../metrics.md) for definitions, units, and observation coverage.

## Download records

Open the run's Artifacts to download HTTP configuration, metrics, and per-request records, including failure reasons. Quiet runs also retain `run.log`; for sweeps and comparisons, the parent run's log covers shared service preparation and cleanup.

Warmup is excluded from performance metrics and panels. Its records remain in the `benchmark-warmup` artifact. Adding `plot` to `--output local,wandb` saves exported figures locally and in the `benchmark-plots` artifact.

See [output settings](../../README.md#read-and-save-results) for other destinations. W&B publication failures make the command fail and preserve the local execution files for inspection.
