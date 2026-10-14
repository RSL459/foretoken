<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce TTFT: Balance Prefix Reuse Against Queueing

English | [简体中文](reduce-ttft-balancing-cache-reuse-and-queueing_zh.md)

A cached prefix saves computation only after the selected worker can run the request. Sending every shared-prefix request to the warmest replica can create a queue whose delay exceeds the saved prefill. The goal is lower user-visible first-token latency, not the largest cache-hit percentage.

## Current upstream behavior

Dynamo's current worker selector charges prefill backlog, decode cost, and active requests while crediting overlap. It can decay device-cache credit when a worker's prefill backlog exceeds the least-loaded eligible worker. AIBrix's current prefix-routing documentation describes normalized cache/load blending, with a default documented score of `5 × prefix + 4 × load_balance`; it also has a cache-first mode with load qualification. Production Stack's load-aware router scores matched-token ratio minus a relative in-flight-load penalty. llm-d supplies separate prefix, queue, load, and latency scorers that can be composed.

Foretoken already offers `kv_least_loaded`, `prefix`, `token_load`, and `two_tier`. Its cache weights express preferences, not measured transfer-time predictions. The open questions are how to calibrate the opportunity cost and maintain useful rankings as queues change.

## A routing decision in milliseconds

For a 10K-token input, worker A has a 9K-token reusable prefix and worker B has none. Suppose the observed service model estimates 30 ms of remaining prefill on A, 220 ms on B, and queue waits of 300 ms and 20 ms respectively. Estimated TTFT is then 330 ms versus 240 ms, ignoring equal overheads: B is the better choice despite its miss. If A's wait falls to 40 ms, A becomes preferable.

A useful decomposition is:

`estimated_TTFT = ingress_wait + worker_wait + cache_ready_time + uncached_prefill_time + response_overhead`.

This is an analysis model, not the exact formula used by every router. Cache-ready time depends on where the state resides and whether it is usable before scheduling; an advertised prefix is not necessarily ready device memory.

Preble estimates recent compute load, new-request prefill cost, and cache-eviction consequences. DualMap's February 2026 method limits each request to two hash-derived candidates, prefers reuse, and switches to the less-loaded candidate when estimated TTFT violates its SLO. Adaptive prefix keys distribute hot prefixes while retaining locality for colder ones. Queued migrations target the precomputed backup and require estimated positive latency benefit. Restricting selection and migration to two candidates bounds search and coordination costs.

## What to reuse and what to test

Dynamo's cited selector computes a block-based cost, not calibrated milliseconds. Its overlap-credit decay normalizes excess prefill backlog by the incoming request's size. Production Stack uses in-prefill plus in-decoding request counts; a count of two long prefills can be more work than ten short decodes. AIBrix's normalized blended score likewise depends on candidate distributions. llm-d's predictive latency scorer is another existing option, with explicit prediction and fallback behavior.

These approaches are appropriate when prefix reuse is substantial and demand is uneven. At low load, affinity often wins; at high load, its hotspot penalty grows. Rapid eviction, burst arrivals, different worker speeds, and stale metrics can reverse rankings. A session key preserves placement but does not by itself prove that the session's KV remains resident.

The engine owns cache validity, allocation, and iteration scheduling. Foretoken's request layer owns candidate eligibility, scoring, and dispatch accounting. Cluster orchestration owns capacity and placement. Router-local observations must be labeled as local when several frontends send to the same worker.

## Experiment and open question

Replay a mixed workload with one increasingly hot prefix family, several cold families, and periodic continuation requests. Hold input/output lengths and aggregate offered rate constant while changing hot-family concentration. Compare current cache/load blending, load-only selection, affinity-only selection, and a cost-calibrated candidate. Add controlled observation delay and actual prefix eviction.

Report TTFT distributions, goodput under a declared TTFT/TPOT objective, uncached tokens executed, per-worker prefill backlog, selection imbalance, cache-hit ratio, and routing overhead. Explain whether a miss was chosen because it was genuinely faster or because observations were wrong.

The remaining design space is robust calibration of queue cost and cache-ready cost under uncertain observations.

## References

- [Preble, 2407.00023v2, 2024-10-03](https://arxiv.org/html/2407.00023v2): execution-time-aware exploitation/exploration and eviction cost.
- [DualMap, 2602.06502v1, 2026-02-06](https://arxiv.org/html/2602.06502v1): two-candidate routing and SLO-aware cache/load fallback.
- [Dynamo selector, commit 7708f041](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kv-router/src/scheduling/selector/reference.rs): implemented backlog and overlap-credit decay.
- [AIBrix prefix routing, commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/docs/source/features/gateway-routing/prefix-cache-aware-routing.rst).
- [Production Stack routing, commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py).
- [llm-d prefix scorer, commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/scorer/prefix/README.md).
- [Foretoken routing](../../../../data-plane/frontend/src/router/README.md).
