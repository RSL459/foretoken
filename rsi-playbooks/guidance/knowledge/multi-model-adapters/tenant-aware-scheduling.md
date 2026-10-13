<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Adapter scheduling under heterogeneous ranks and deadlines

English | [简体中文](tenant-aware-scheduling_zh.md) | [Multiple models and adapters](README.md)

## Why aggregate throughput misses the problem

A tenant using rank 128 may consume more adapter compute and residency than one using rank 8. A latency-sensitive tenant and a relaxed tenant should not be evaluated through one average TTFT. Grouping all requests that share the base model is already possible; the question is which requests should share a batch and device when ranks, popularity, and deadlines differ.

LoRAServe, submitted in November 2025, studies rank-aware distributed placement and routing. HALO, submitted 2026-10-04, studies multi-SLO scheduling and base/LoRA execution overlap. They address different boundaries: where adapter requests go versus when their prefill/decode work executes. Neither paper alone supplies a complete tenant-service implementation.

## One scheduling decision

LoRAServe estimates each adapter's token demand from recent traffic and uses pre-profiled rank-specific serving capacity under an SLO. It computes budgets per rank, packs demand into server assignments, routes with fractional probabilities, and rearranges assignments to reduce movement. For adapter a, routing fractions sum to one. Two equally popular adapters with different ranks need not consume equal server capacity, and packing similar ranks can reduce inefficient heterogeneous batches.

On a serving worker, HALO computes request slack relative to the next deadline. Prefill is constrained by TTFT; decode has per-token TBT deadlines. A request with buffered generated tokens may have enough slack to skip a decode iteration, leaving capacity for an urgent request. The system separates generation from client release through an output queue, so token-generation timestamps and client-visible delivery timestamps are distinct measurements.

HALO also overlaps base and LoRA computation during decode with tuned SM allocations. The independent paths consume the same input, then combine at the adapted layer's result. A feedback search profiles allocations rather than assuming equal shares. Its reported contribution does not improve prefill through the same base/LoRA parallelism. This mechanism must be compared with the current engine's existing execution overlap, not treated as a capability that all engines lack.

## Conditions, weights, and costs

These methods use compatible base models and trained adapter weights, not a new training objective. Preserve checkpoint identity, target modules, ranks, scales, tokenizer, and task quality. Synthetic adapters can exercise rank diversity but cannot establish tenant usefulness. Dense decoder evidence does not automatically cover MoE LoRA, multimodal tower adapters, quantized kernels, or a different TP layout.

LoRAServe's evaluated setup uses NVIDIA A100 and InfiniBand/GPUDirect RDMA for remote adapter fetching. Its placement depends on profiled operating points and recent traffic. HALO's SM-partitioned execution similarly depends on supported GPU/runtime controls; dtype and actual kernel path must be recorded. Altered scheduling should preserve intended model computation, but reduction order or a different concurrent kernel can still affect numerical reproducibility.

Batch consolidation trades utilization against waiting. Popularity-aware decisions can starve rare adapters; deadline-aware decisions can improve urgent traffic while hurting relaxed traffic. Output buffering can smooth delivery but also postpone tokens, so a delivery metric alone is insufficient to attribute a compute gain.

## Experiments that test the policies

Replay a trace with independent rank, popularity, input length, output length, and SLO labels. Include popularity reversals, sudden urgent bursts, and rare high-rank requests. Compare rank-agnostic versus rank-aware routing at identical worker capacity; separately compare FIFO versus slack-aware worker scheduling with identical routes. Finally compare sequential versus SM-overlapped adapter execution at matched batch membership.

Report each tenant's P95/P99 TTFT and TBT, completed tokens, failures, queue age, deadline misses, generated-versus-released token timestamps, and SLO-qualified goodput. Measure adapter migrations, bytes transferred, switch cost, CPU/GPU queue time, and SM partition efficiency. Retain total offered demand so dropping inconvenient requests cannot masquerade as improvement.

If rank-aware placement helps only static popularity, investigate forecast lag and migration cost. If client TBT improves without faster generation, buffering accounts for that result. If urgent goodput rises by starving rare tenants, the policy needs a stated fairness objective. The remaining research is joint cost/deadline reasoning with measurable tenant outcomes, not repackaging basic multi-LoRA serving.

## Sources and checked state

Checked 2026-10-14.

- [LoRAServe, arXiv:2511.22880v1](https://arxiv.org/html/2511.22880v1): method, remote-transfer path, and evaluated workloads. This version promises code/traces after acceptance but supplies no author repository; later availability is not inferred.
- [HALO, arXiv:2610.04956v1](https://arxiv.org/html/2610.04956v1): submitted 2026-10-04; slack scheduling, SM search, and output queue. No author code link identified in this version.
- [SGLang LoRA documentation](https://docs.sglang.io/advanced_features/lora.html): existing multi-adapter batching and runtime restrictions; source main checked at `e9400c5`, dated 2026-10-13. Paper proposals are not assigned an upstream PR state without evidence.
