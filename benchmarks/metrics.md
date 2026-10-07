# Performance metrics

English | [简体中文](metrics_zh.md) · [Performance examples](docs/perf/README.md)

Read request success first, then compare latency and throughput for the same workload. `metrics.json` contains aggregates; `raw_output.json` contains individual request records.

## Request metrics

| Metric | Meaning |
| --- | --- |
| Success rate | Successful requests divided by attempted requests |
| End-to-end latency (E2EL) | Request duration; successful streams end at the last chunk with non-empty `choices` |
| TTFT | Request start to the first chunk with non-empty `choices` |
| TPOT | `(E2EL − TTFT) / (output tokens − 1)`; zero for one output token |
| ITL | Interval between chunks with non-empty `choices`; a chunk may contain multiple tokens |
| Request throughput (req/s) | Successful requests divided by measured run duration |
| Input/output token throughput (tokens/s) | Successful requests' corresponding token total divided by measured run duration |
| Benchmark duration (s) | Measured run duration, including completion of in-flight requests |
| Mean reported cached input tokens | Mean `usage.prompt_tokens_details.cached_tokens` among successful requests reporting it |

Latency distributions use successful requests. P50, P95, and P99 are the corresponding request percentiles. `--no-stream` retains latency and throughput but omits TTFT, TPOT, and ITL; usage-only chunks do not advance streaming timing.

Token counts come from service-reported usage. A missing input or output count makes aggregates needing that complete total unavailable. TPOT also needs output usage and streamed timing. Cached input tokens describe the reported reuse count, not a storage-tier or KV-store hit rate.

Raw JSON timings use seconds. Charts use seconds for TTFT and E2EL, milliseconds for TPOT and ITL. Retries are disabled by default; with `--max-retries N`, retry time is part of logical request latency.

## Concurrency and normalized throughput

| Metric | Meaning |
| --- | --- |
| `max_concurrency` | Configured limit: requests for single-turn and trace workloads, conversations for multi-turn data |
| `request_concurrency.peak` | Highest number of simultaneously active HTTP requests |
| `request_concurrency.mean` | Total request duration divided by run duration, including failed requests |
| Output tok/s / user | Output throughput divided by the configured concurrency; unlimited concurrency uses measured mean active requests |
| Output tok/s / GPU | Output throughput divided by the selected deployment's resolved GPU count |

Each HTTP turn is a request. A failed turn stops its conversation; completed conversations are counted separately from successful turns. [Mixed workloads](docs/perf/multi-dataset.md) report dataset, model, and request-class breakdowns, each using the complete run duration.

## Curves

| Curve | Calculation |
| --- | --- |
| Time | One-second completion windows; all tokens from a successful request are counted when it finishes |
| Cumulative | Completed successful request or token totals divided by elapsed time |
| Request index | Individual records in send order |

Time curves include throughput, active requests, failures, and latency percentiles. Client curves cover this benchmark's traffic; Grafana and Prometheus service metrics cover all traffic reaching the model. Trace replay adds `replay_delay`, the gap between scheduled arrival and actual send; trace end-to-end timings include that delay.

## SLO results

With `--slo-params`, a request meets its service-level objective (SLO) when it succeeds and satisfies every timing condition. Failed requests and missing required timing values count as not meeting the SLO.

| Result | Calculation |
| --- | --- |
| Attainment | Requests meeting the SLO divided by all measured requests |
| Request goodput | Requests meeting the SLO divided by run duration |
| Token goodput | Output tokens from those requests divided by run duration |
| `slo_met` | Per-request decision in raw results and W&B request history |

One-second completion windows use the same definitions, including failures in attainment's denominator. Windows without completions have no attainment value. The run summary scores all measured requests together rather than averaging window fractions. Repeated sweeps average per-run values. [SLO concurrency search](docs/perf/slo.md) instead evaluates aggregate criteria to find the highest observed passing request peak.

## GPU allocation

Kustomize runs record allocated GPU counts alongside load and Ready replicas. `gpu_allocation.json` retains samples and observation gaps; `metrics.json` reports `gpu_seconds`, `gpu_hours`, and coverage by device resource name.

Whole-run totals require full coverage. `observed_gpu_seconds` is the area covered by partial observations, not a whole-run cost. Device types are reported separately. Allocation measures reserved capacity rather than GPU utilization.

## Speculative decoding observations

With a Kustomize service and Prometheus, runs report draft acceptance, accepted tokens per draft iteration, mean draft and target-forward GPU times, and each stage's share of their combined time.

The target-forward stage includes batch verification, excluding sampling and rejection. Stage times describe GPU work, not request latency or speedup. These counters include all traffic to the selected service.

`metrics.json` and W&B Summary estimate values from counter increases during the measured window, accounting for resets. Time curves use trailing five-minute rates instead. Short runs or absent counters can leave estimates unavailable; repeated sweeps summarize available per-run estimates with mean and standard deviation.
