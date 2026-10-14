<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Parallelism and Communication

English | [简体中文](README_zh.md)

Follow the dependency that delays the next useful computation, not just the longest communication kernel.

- Does MoE dispatch/combine dominate small decode steps? [Hide MoE Communication Through Microbatch and Block-Level Overlap](hide-moe-communication-through-microbatch-and-block-overlap.md) explains current DeepEP V2.5, vLLM DBO, branch-specific SBO, and SM contention when useful independent work is limited.
- Does adding TP ranks increase synchronization faster than it reduces computation? [Reduce TP Synchronization Through Shape-Aware Collective Selection](reduce-tp-synchronization-through-shape-aware-collective-selection.md) follows all-reduce/AG/RS ownership, eager versus registered graph buffers, and MNNVL-specific selection.
- Is long-context work or KV history spread across ranks incorrectly or inefficiently? [Scale Long-Context Attention Through Query and KV Sharding](scale-context-attention-through-query-and-kv-sharding.md) distinguishes Ulysses/ring prefill, causal balancing, paged-history DCP, and normalized partial-output merging.
- Does cross-node PP fit the model but leave stages idle? [Balance Pipeline Latency and Throughput Through Microbatching](balance-pipeline-latency-and-throughput-through-microbatching.md) separates serial request latency from occupancy, stage balance, and supported transfer primitives.
- Is expert compute balanced while slow links remain overloaded? [Balance Expert and Network Load: Topology-Aware Replica Placement](balance-expert-network-load-through-topology-aware-replica-placement.md) connects logical routing groups, node-local replicas, replica graphs, and migration traffic.

For local expert kernels, small-batch scheduling, quantized representations, and the two balancing timescales, see [MoE execution](../moe-execution/README.md). Validate on the real rank/GPU/NIC topology using [deployment recipes](../../../../examples/recipes/README.md), [performance evaluation](../../../../benchmarks/docs/perf/README.md), and separate [profiling captures](../../../../benchmarks/docs/profile/README.md). Complete the model-quality comparison through [quality evaluation](../../../../benchmarks/docs/eval/README.md).

Return to [inference knowledge](../README.md).
