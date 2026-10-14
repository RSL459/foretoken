<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Token-Load State

English | [简体中文](token-load-state_zh.md)

## Problem and mechanism

Ten 256-token prompts and ten 32K-token prompts have the same queue depth but radically different work and KV residency. Even equal token counts can differ when one batch reuses prefixes or concentrates traffic on one DP rank. Capacity decisions need a state vector rather than a single request-count surrogate.

Useful dimensions are uncached queued prefill tokens, scheduled decode context tokens, queued decode context demand, KV capacity/occupancy, active requests, ready workers and observed service rates. Keep units explicit. Queued token work divided by calibrated prefill tokens/s estimates backlog seconds; resident context tokens divided by KV token capacity estimates memory pressure. Neither is automatically a TTFT prediction.

An arithmetic example has two equal-capacity ranks at 0.95 and 0.15 KV pressure. The average 0.55 looks comfortable, but the hot rank may stop admitting requests. Adding a replica may help only if routing redistributes work. Conversely, a high count of reusable-prefix tokens can occupy cache without requiring proportional prefill compute. Include the uncached suffix and account for shared blocks rather than adding every request's raw length indiscriminately.

For mixed models, raw tokens/s is not comparable service. The 2026 TRE paper proposes `TSS_raw = (w_p*r_prefill + r_decode)/(active + w_q*waiting)` and normalizes its smoothed value by a model/SLO-specific healthy boundary θ. Here r_prefill and r_decode are processed tokens/s over the same window, active and waiting count requests, and w_p and w_q are dimensionless prefill-service and waiting-demand weights. TSS_raw and θ have units of weighted tokens/s per weighted outstanding request. The normalized value is dimensionless; a value below 1 identifies a deficit relative to that calibration. Weights and healthy thresholds depend on workload and runtime.

## Hardware, dtype and costs

KV pressure follows actual full-attention, MLA, sliding-window or hybrid-state allocation. Weight dtype and cache dtype are distinct. Changing BF16 KV to FP8 alters capacity and may require quality validation; changing only weight precision can speed compute without reducing context residency. TP and DP layouts determine which counters are duplicated or partitioned.

Output lengths are unknown at admission. Estimated future decode work can overcount early EOS or undercount long generations. Router-side in-flight work, scheduler queue state and physically allocated cache describe different lifetimes. Their collection and synchronization cost should be weighed against the decisions they improve; a stale high-detail vector can be worse than a fresh coarse signal.

## Public implementation and current scope

Checked 2026-10-14. Foretoken's [token-load algorithm](../../../../control-plane/internal/autoscaling/algorithm/decision/token_load.go) evaluates each engine separately. Prefill presets normalize queued tokens by context length, while custom `load` mode uses absolute queue tokens. Decode uses scheduled plus queued context demand divided by KV capacity; aggregate adds queued prefill. One hot engine can request an extra Group; removal checks all engines and estimates redistributed pressure. Its [guide](../../../../docs/autoscaling.md) limits observations to a single full-attention cache group with PCP/DCP=1; encoder pools and targets with unavailable, incomplete, or stale observations retain current capacity within configured replica bounds.

llm-d's [in-flight producer](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/requestcontrol/dataproducer/inflightload/producer.go) discounts prefix hits, releases prefill contribution at stream start and removes request state at stream end/TTL eviction. Endpoint deletion also removes metric series. Its [P/D prefill trigger](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/keda-epp-token-aware/pd-disaggregation/base/prefill-scaledobject.yaml) sums backlog tokens and divides by measured throughput; the [decode trigger](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/keda-epp-token-aware/pd-disaggregation/base/decode-scaledobject.yaml) sums decode-pod KV fractions.

[TRE](https://arxiv.org/html/2609.29160v1) provides a Kubernetes hot-switch research prototype for colocated P/D and calibrated service thresholds, with a [public artifact](https://github.com/zxzx9898/Token-service-share_Rebalancing_Engine).

## Experiments and remaining questions

First hold request count constant while changing lengths, prefix hits and rank skew. Compare queue-only, aggregate token pressure and per-rank state in a replay model. Include removed-endpoint counters and early EOS to expose stale estimates.

On real services, collect router estimates, scheduler state and cache occupancy simultaneously. Measure their error against completed tokens and actual residency; correlate scale decisions with SLO goodput and ready capacity. Test a length-mix change at constant request rate. Remaining questions are output-length uncertainty, hybrid-state demand semantics and calibrated cross-model sharing. Fast routing decisions belong in [routing and admission](../routing-admission/README.md), not the autoscaler's lifecycle.

[Back to autoscaling and placement](README.md)
