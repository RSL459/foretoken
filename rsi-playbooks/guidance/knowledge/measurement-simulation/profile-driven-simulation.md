<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Profile-driven simulation and model mismatch

English | [简体中文](profile-driven-simulation_zh.md) · [Measurement and simulation](README.md) · [Knowledge](../README.md)

## What a simulator can replace

A simulator can cheaply explore batch limits, parallelism, and routing configurations after expensive device measurements establish a runtime model. It cannot infer an unmodeled execution dependency from accurate kernel timings. The useful question is which decisions remain reliable inside the calibrated design space, not whether one global error percentage licenses every prediction.

Vidur separates profiling, runtime estimation, and event-driven scheduling. The MLSys 2024 paper groups operators into token-level, sequence-level, and communication work. Token-level costs depend mainly on current token count; attention also depends on request history; collectives depend on message size and topology. Its runtime estimator uses random forests to interpolate measured shapes, and the simulator applies scheduling and memory-management behavior around those costs.

## A compact feature can lose an important distinction

For prefill attention, the paper approximates a batch of sequences with lengths lᵢ by a single sequence of equivalent length `l_eq = √(Σ_i lᵢ²)`, preserving the quadratic work estimate. For memory-bound decode attention, it models aggregate KV reads, relying on evaluated kernels handling length skew effectively. These are useful reductions under specific kernel assumptions. Two batches with equal total context can still differ in partition count, maximum length, occupancy, launch count, or backend dispatch. A replacement attention kernel may invalidate the old feature reduction without changing the model architecture.

MoE adds expert-load distribution; speculative decoding adds acceptance-dependent state transitions; hybrid attention adds different persistent state and scheduling constraints. A simulator whose current path does not consume those features cannot capture them merely by increasing training data. The inspected Vidur README documents its model/hardware support matrix and lists canary work separately as experimental.

CPU costs are another mismatch source. Vidur's profiling documentation lists optional implementation-specific CPU overhead profiling and says it is currently undocumented. Missing scheduler, sampling, detokenization, or output overhead can matter most when device steps become short. Serially adding all CPU and GPU costs is not the fix either: an engine that overlaps them needs the corresponding dependency model.

## Small errors can change the future queue

Suppose a simulator underestimates an iteration by δ milliseconds over k iterations. For an isolated fixed sequence, error can accumulate approximately as kδ. Under arrivals, the changed completion times alter which requests join the next batch, when KV capacity is released, and whether another request queues. The resulting error is not simply a constant offset.

An illustrative M/M/1 queue has response time 1/(μ − λ). At λ = 90 requests/s, changing assumed capacity from 100 to 95 doubles predicted response time. Real continuous batching does not obey that model, but the sensitivity explains why a small service-time error near capacity can reverse a configuration ranking.

Vidur's paper makes this boundary explicit: static evaluation uses request execution time without scheduling delay, normalized by output length; dynamic evaluation uses end-to-end latency, also normalized by output length, with Poisson arrivals at 85% of measured capacity. Figures 3 and 4 compare the median and P95 of these normalized request latencies: the largest absolute relative discrepancy is 3.33% for static P95 and 8.50% across the dynamic median/P95 results. Each percentage compares a predicted percentile with the corresponding measured percentile, using the measured value as denominator. The evaluated models and engine fork define the scope; raw TTFT, ITL, and overload require separate calibration. Its near-capacity discussion explains how queueing magnifies small prediction differences.

## Calibration that separates two failure models

First replay a fixed sequence of actual batches, if the simulator exposes that boundary, and compare iteration durations for held-out shapes. Preserve phase, context distribution, graph/eager mode, kernel selection, and parallel topology. Structured residuals versus length skew or batch size indicate a runtime-feature mismatch. A constant host-size-dependent residual suggests omitted overhead. An average residual near zero can still hide opposite errors in prefill and decode.

Next run the actual arrival workload through both systems and compare batch composition, admission time, KV occupancy, and completion order as well as percentiles. Good duration predictions with different batches point to scheduler, memory, or arrival semantics rather than kernel modeling. A good median with a wrong burst-recovery curve points to state transitions or queue sensitivity.

For configuration search, retain predicted ranges and rank candidates only where their separation exceeds observed model error. Deploy a small number of promising and deliberately contrasting candidates to test the ranking. Reprofile after a change in hardware, communication topology, runtime, kernel, or graph behavior that changes the modeled mechanism. Simulation reduces the expensive search space; actual service execution establishes performance and quality.

## Sources and verification

Checked 2026-10-14.

- [Vidur, MLSys 2024](https://www.microsoft.com/en-us/research/wp-content/uploads/2024/05/vidur_mlsys24.pdf), §§3–7: operator features, runtime estimator, evaluation population, and near-capacity sensitivity. [arXiv record](https://arxiv.org/abs/2405.05465) identifies the paper and revision.
- [Vidur README](https://github.com/microsoft/vidur/blob/abae7f63aa857300f5cdc6f5e0d27860cd24721b/README.md) and [profiling documentation](https://github.com/microsoft/vidur/blob/abae7f63aa857300f5cdc6f5e0d27860cd24721b/docs/profiling.md): revision dated 2026-08-24; support matrix, canary scope, profiling prerequisites, and CPU-overhead documentation gap.
- [Foretoken timing definitions](../../../../benchmarks/docs/metrics.md): checked at `e6ae3df6`; simulated engine timestamps must not be equated with client-observed chunk timings.
