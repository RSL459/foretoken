<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Diagnose SLO failures through request-level compliance attribution

English | [简体中文](diagnose-slo-failures-through-request-level-compliance-attribution_zh.md) · [Measurement and simulation](README.md) · [Knowledge](../README.md)

## Throughput can rise while useful service falls

Suppose one configuration completes 100 requests/s but only 60 meet the latency requirements. Another completes 80 requests/s and 76 meet them. The second has lower throughput and higher request goodput. If long outputs dominate token totals, token goodput can rank these configurations differently again. The objective must identify which requests count as useful and which resource denominator matters.

For request i, define gᵢ = 1 only when it succeeds and satisfies every required condition; otherwise gᵢ = 0. For a cohort of N attempted requests observed through completion or failure over duration T, request goodput is Σgᵢ/T, token goodput is Σgᵢnᵢ/T for output length nᵢ, and attainment is Σgᵢ/N. T spans measurement start through drain completion, excluding warmup. For fixed steady-state windows, instead count completions in the window and report unfinished work separately. Token goodput requires reported output counts for compliant requests. Failures remain in the attainment denominator; compare matching workload mixtures.

## A joint requirement is not a set of independent percentiles

A request that meets TTFT but violates its worst streaming gap is not jointly compliant. If 95% meet a TTFT threshold and 95% meet an ITL threshold, joint attainment can be as low as 90%; multiplying percentages assumes a dependence structure that has not been measured. Separate aggregate percentiles also cannot identify which requests violate both conditions.

Per-request average TPOT hides stalls. A stream with one 500 ms pause and many rapid chunks can have acceptable average TPOT but unacceptable maximum gap. Conversely, a chunk containing several tokens can have a long received interval without slow per-token device execution. Compare the same timing unit and criterion. Foretoken uses maximum received-chunk interval for a request-level ITL SLO; its TTFT measures the time from request start to the first non-empty `choices` chunk, which may be a role or finish event. These are operational definitions, not universal tokenizer-level meanings.

The cited AIPerf metrics reference uses an average decode interval and a reciprocal per-user throughput convention. Matching names alone is therefore insufficient when comparing tools. Match the formula, token-count source, first-event rule, failure population, and observation window.

## Tail attribution must preserve the selected requests

For a sequential decomposition, total latency L = Q + P + D + O may include waiting, prefill, decode, and output delivery. However, p99(L) is not p99(Q) + p99(P) + p99(D) + p99(O). Different requests can dominate each component, and pipelined stages may overlap. Instead select the requests in the end-to-end tail, then inspect their stages and workload characteristics.

For example, long-input requests may dominate TTFT while long-output requests dominate E2EL. A mixed-workload optimization can improve aggregate p99 simply by changing which class completes successfully. Report per-class attainment and attempt counts alongside the aggregate. The same concern applies to cancellation: dropping slow requests can improve successful-only latency while lowering useful completions.

Quantiles also carry sampling uncertainty. With 100 observations, a p99 estimate is essentially controlled by the largest few values and the estimator's interpolation convention. More tokens from one request do not create more independent request samples. Consecutive requests within the same overload burst are correlated, so a request-wise bootstrap can understate uncertainty; resampling independent runs or time blocks better respects the workload structure.

## Discriminating experiments

Hold the request population and external arrival schedule fixed. Sweep load around the point where goodput ceases to scale, preserving failed, timed-out, and missing-metric attempts. Inspect per-request joint compliance and separately attribute violations to first response, maximum stream gap, and completion latency. If token throughput rises while the compliant fraction falls, the configuration is exploiting more batching or serving more long outputs rather than necessarily improving interactive service.

For tail causes, compare equal-length cohorts and align requests to overload intervals, cache misses, CPU throttling, and rank delays. A request-level correlation suggests a mechanism but does not establish it; change the suspected resource while leaving demand fixed. For example, removing quota pressure that reduces stream-gap violations but not prefill time identifies a different boundary from a prefill kernel improvement.

Finally preserve the time denominator. Foretoken's one-second token curves assign all request tokens to the completion window; a spike is not an instantaneous device token-production rate. Run duration, admission duration, and steady-state observation duration answer different questions. Report the actual window with goodput, and do not average window attainment fractions to reproduce a whole-run ratio with unequal counts.

## References

- [Foretoken metric definitions](../../../../benchmarks/docs/metrics.md), [chunk timing](../../../../benchmarks/src/benchmarks/integrations/streaming.py), and [HTTP runner](../../../../benchmarks/src/benchmarks/runs/http.py): at `e6ae3df6`; joint criteria, failures, received chunks, and completion-window curves.
- [AIPerf metrics reference](https://github.com/ai-dynamo/aiperf/blob/e1daadd10faa395100384358131d784d6858c5ae/docs/metrics-reference.md) and [effective metrics](https://github.com/ai-dynamo/aiperf/blob/e1daadd10faa395100384358131d784d6858c5ae/docs/reference/effective-vs-active-metrics.md): 2026-10-12 revision; metric populations and normalization differ.
- [Vidur, MLSys 2024](https://www.microsoft.com/en-us/research/wp-content/uploads/2024/05/vidur_mlsys24.pdf), §§7.2–7.3: near-capacity error amplification and workload-dependent SLO/cost trade-offs in the evaluated systems.
