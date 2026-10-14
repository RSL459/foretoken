<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce request latency through topology-aware cache placement

English | [简体中文](reduce-request-latency-through-topology-aware-cache-placement_zh.md)

## Problem and mechanism

A new replica can increase compute capacity while reducing cache reuse or overloading a shared cache link. Placement decides where capacity and state live; routing decides which request consumes them. A cache index answers where reusable state is reported, but does not itself place workers, reserve bandwidth, or move the data.

For each feasible worker location, estimate `T = queue + restore + uncached_prefill + decode`. Local GPU hits, host-memory restoration and remote shared-cache hits have different cost. Cache compatibility comes first: checkpoint, positional semantics, dtype and connector layout must allow reuse. Then compare saved compute with state movement and contention.

An illustrative request can restore 3 GiB of remote prefix KV or recompute that same prefix in 40 ms. A 20 GB/s effective remote path needs at least 161 ms before setup and queueing; maximizing hit length would choose the wrong target. If recomputing that prefix takes 500 ms instead, restoration may win. Both alternatives still process the uncached suffix. A weighted hit score is a useful preference but is not a calibrated transfer-time estimate.

Placement should also consider the future footprint. Putting all warm prefixes in one domain improves affinity but creates a fan-in hotspot and a failure concentration. Replication reduces contention at the cost of memory and network warmup. Independent cold replicas may spread compute yet repeatedly regenerate the same prefix. Under a fixed GPU budget, a placement decision can improve one model while forcing another below its SLO floor.

## Hardware, models and costs

Topology includes GPU–NIC affinity, NVLink/NVSwitch domains, rack links, host NUMA and shared-storage bandwidth. Dense BF16 full-attention KV can be much larger than MLA state; hybrid models also require multiple state types. FP8 weights do not make remote KV cheap. TP layouts may require gathering or replication before restore.

Count cache-warmup bytes, duplicate weights, shared-store capacity, and losses when retiring workers. A node with cached weights can start faster without having warm request KV; these are separate placement benefits. Static quota admission likewise does not guarantee that a granted accelerator is near the needed cache or partner stage.

## Current implementation and evidence

llm-d's [cost-aware-memory implementation](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/kvcache/kvblock/cost_aware_memory.go) manages estimated index-memory cost with bounded stores. `DeviceTier` contributes to index-memory accounting, and lookup walks available prefixes; worker allocation and data movement have separate owners.

Production Stack's [routing implementation](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py) already contains LMCache-backed prefix lookup and load/cache scoring. It refreshes live endpoint/instance mappings; this is request routing rather than an automatic cache migration service. llm-d's [Kueue guide](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/kueue-rebalancing/README.md) provides per-model quota floors, borrowing and preemption below HPA, not cache-locality optimization.

Foretoken's [routing owner](../../../../data-plane/frontend/src/router/README.md) already distinguishes GPU-local cache credit from restored extensions, defaults `restoreWeight` to 0.5, and balances per-rank request pressure. The document explicitly says these weights are preferences, not transfer estimates; Encoder/Decode use load alone.

The 2026 [AFD design-space study](https://arxiv.org/html/2605.28302v1) models the impact of placing P/D partners on scale-up versus scale-out links for FP8 MoE on B200. Its network estimates motivate comparisons of partner placement and shared-link contention.

## Discriminating experiments and remaining questions

First replay routing against a fixed placement graph with measured link service curves. Vary warm-prefix concentration, restore bandwidth and cache capacity independently. Compare local-only affinity, longest-hit routing, load-only routing and latency-cost estimates. Include concurrent restore flows so a perfect isolated transfer model cannot hide shared-link congestion.

Then run real multi-turn services with identical content and arrival schedules. Compare concentrated and spread workers at equal hardware budget. Record local/remote hits, restored bytes, lookup latency, TTFT, ready capacity, shared-link utilization and post-scale cache warming. Add one placement change while keeping routing fixed, then one routing change while keeping placement fixed, to establish attribution. Remaining problems include stale index observations, tail-aware joint placement and eviction-aware scaling. Cache internals are in [KV-cache knowledge](../kv-cache/README.md); stage constraints are in [disaggregated serving](../disaggregated-serving/README.md).

[Back to autoscaling and placement](README.md)
