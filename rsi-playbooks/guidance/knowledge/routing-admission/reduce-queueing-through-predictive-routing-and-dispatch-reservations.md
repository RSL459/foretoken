<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce Queueing: Predictive Routing and Dispatch Reservations

English | [简体中文](reduce-queueing-through-predictive-routing-and-dispatch-reservations_zh.md)

Queue depth describes how many requests are waiting, not how much work precedes the next arrival. Routing improves when it estimates the request's incremental latency on each candidate and promptly accounts for dispatches that have not yet appeared in engine telemetry.

## What current routers already estimate

Dynamo's current selector combines active prefill tokens, cache overlap, decode cost, and active-request pressure. It is a work-based score, not simply least-request routing. Production Stack's load-aware implementation uses current router monitor statistics even after tokenization and cache lookup, but represents load as in-prefill plus in-decoding request counts. AIBrix already exposes a Preble strategy in addition to prefix/load blending.

llm-d's current predicted-latency producer and latency scorer go further: an XGBoost sidecar predicts endpoint TTFT and TPOT; request lifecycle hooks track in-flight work; endpoint attributes carry predicted latency and SLO headroom.

## Work prediction versus request counting

Suppose A has three queued 16K-token uncached prompts and B has ten 128-token prompts. Queue depth prefers A, but prefill work can prefer B. Next suppose the incoming prompt has a large prefix on A: incremental uncached work may reverse that ranking again. Preble estimates execution costs from profiled token-dependent functions and includes recent load and eviction costs. DualMap uses pending prefill tokens to estimate first-token pressure within its two-candidate architecture.

An analysis model is `finish_estimate = current_wait_estimate + incremental_service_estimate`. Its inputs should distinguish uncached input, current context lengths, active decode population, and worker configuration. Calibration belongs to a specific model, dtype, backend, topology, and parallelism configuration. A predictor can be systematically wrong after quantization, kernel, or graph settings change.

Telemetry delay introduces a separate problem. Ten requests arriving between two engine samples can all choose the endpoint that looked idle in the previous sample. Immediate dispatch reservations represent that unseen work until the owning lifecycle reconciles it with execution or completion. They must be released on errors and cancellation. If measured load already includes a reserved request, adding both values double-counts it. The correction needs an explicit observation boundary, not another independent global counter.

## Inspect the actual prediction semantics

llm-d's producer computes headroom from `SLO - predicted_latency` with a configurable buffer factor. Its current scorer first separates endpoints by predicted headroom. If no endpoint has prediction data, it falls back to a composite of KV availability, queue size, and prefix match. If every predicted endpoint violates an objective, it prefers idle candidates when available; otherwise it selects a less-severe deficit bucket. It does not necessarily reject the request.

Missing prediction data can remain in the nonnegative candidate group with zero headroom. This detail is important for evaluation: partial sidecar failure is not equivalent to the all-missing fallback. The producer documentation also says non-streaming TTFT training uses EOS, effectively measuring end-to-end latency; TPOT is neutralized. Streaming and non-streaming labels therefore cannot be mixed as though they represented identical first-token observations.

## Ownership and applicability

The engine publishes execution and cache observations. Foretoken's request layer owns selection, dispatch reservations, and lifecycle release; its existing request ledger is a relevant owner to inspect before proposing another counter. Cluster orchestration owns capacity changes. Prediction serving may be an external adapter, but the router still owns how missing or inaccurate predictions affect selection.

Prediction is most valuable for heterogeneous request shapes and sustained contention. At low load, predictor latency can outweigh its benefit. Bursts, stale state, and changed workloads require checking ranking accuracy, not just average regression error. A model with low mean error can still select the wrong worker for deadline-critical requests.

## Experiment and remaining question

Replay timestamped arrivals with short and long inputs, cache-hot continuations, and burst intervals. Compare current work/count scores with a predictor using the same candidate set. Separately vary metric sample delay, sidecar response delay, and partial prediction availability; do not change all three at once.

Record predicted versus observed TTFT/TPOT, pairwise ranking errors, queue residence, router overhead, per-worker assignments, p99 token gaps, and SLO-qualified completions over all arrivals. Compare dispatch-time predictions with observations of the same request, rather than unrelated endpoint averages. Include completion and cancellation paths when checking outstanding work.

The remaining design space is reliable calibration and reconciliation under changing execution conditions. Compare any new predictor against well-tuned existing work-based scorers, not only request counts.

## References

- [Preble v2, 2024-10-03](https://arxiv.org/html/2407.00023v2) and [DualMap v1, 2026-02-06](https://arxiv.org/html/2602.06502v1): cost prediction at routing boundaries.
- [llm-d predicted-latency producer, commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/requestcontrol/dataproducer/predictedlatency/README.md): lifecycle hooks and label semantics.
- [llm-d latency scorer code, same revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/scorer/latency/plugin.go): actual grouping and fallback behavior.
- [Dynamo selector, commit 7708f041](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kv-router/src/scheduling/selector/reference.rs).
- [Production Stack routing, commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py).
- [AIBrix routing documentation, commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/docs/source/features/gateway-routing/prefix-cache-aware-routing.rst).
