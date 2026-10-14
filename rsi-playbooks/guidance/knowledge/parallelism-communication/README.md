<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Parallelism and Communication

English | [简体中文](README_zh.md)

Follow the dependency that delays the next useful computation, not just the longest communication kernel.

- Does MoE dispatch/combine dominate small decode steps? [Low-latency dispatch and overlap](low-latency-dispatch-overlap.md) explains current DeepEP V2.5, vLLM DBO, branch-specific SBO, and SM contention when useful independent work is limited.
- Does adding TP ranks increase synchronization faster than it reduces computation? [TP collective granularity](tensor-parallel-collective-granularity.md) follows all-reduce/AG/RS ownership, eager versus registered graph buffers, and MNNVL-specific selection.
- Is long-context work or KV history spread across ranks incorrectly or inefficiently? [Context-parallel layouts](context-parallel-layouts.md) distinguishes Ulysses/ring prefill, causal balancing, paged-history DCP, and normalized partial-output merging.
- Does cross-node PP fit the model but leave stages idle? [Pipeline microbatch bubbles](pipeline-microbatch-bubbles.md) separates serial request latency from occupancy, stage balance, and supported transfer primitives.
- Is expert compute balanced while slow links remain overloaded? [Topology-aware expert placement](topology-aware-expert-placement.md) connects logical routing groups, node-local replicas, replica graphs, and migration traffic.

For local expert kernels, small-batch scheduling, quantized representations, and the two balancing timescales, see [MoE execution](../moe-execution/README.md). Validate on the real rank/GPU/NIC topology using [deployment recipes](../../../../examples/recipes/README.md), [performance evaluation](../../../../benchmarks/docs/perf/README.md), and separate [profiling captures](../../../../benchmarks/docs/profile/README.md). Complete the model-quality comparison through [quality evaluation](../../../../benchmarks/docs/eval/README.md).

Return to [inference knowledge](../README.md).
