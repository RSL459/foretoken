<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Persistent Tile Scheduling

English | [简体中文](persistent-tile-scheduling_zh.md)

Use this when a matrix kernel spends time on poorly filled tile waves, repeated setup, or weak cache reuse despite efficient tensor-core instructions.

## What persistence changes

A conventional tiled GEMM launches one thread block for each output tile. For tile dimensions `BM × BN`, the output contains `ceil(M/BM) × ceil(N/BN)` tiles. A persistent kernel instead launches a bounded set of blocks and lets each block process a sequence of tiles. Its operand pipeline and accumulator machinery can survive across that sequence.

Suppose there are 100 output tiles and 80 resident workers, with equal tile costs. Twenty workers execute a second tile while the other sixty finish early. Persistence does not eliminate this final partial wave. It changes how work is assigned and how setup, loads, computation, and stores overlap. A scheduler that improves locality can still lose through load imbalance.

The current Triton Gluon persistence tutorial implements both a simple tile order and a grouped order intended to improve reuse. CUTLASS already provides persistent cooperative and ping-pong kernels. The research question is which scheduling and resource allocation fit the actual inference shapes, rather than whether to introduce persistence at all.

## Follow an output tile

A producer issues asynchronous Tensor Memory Accelerator (TMA) loads into a shared-memory ring. A barrier records the expected transfer size. A consumer waits for the slot, performs matrix operations, and releases the slot before the producer overwrites it. After reduction over K, an epilogue converts and stores the output. Rotating that epilogue across tile boundaries allows the previous tile's store to overlap the next tile's computation.

The Gluon example selects Hopper warp-group MMA or Blackwell `tcgen05`. Hopper accumulators consume registers; the Blackwell path uses tensor memory. Operand and output-buffer lifetimes determine how much shared memory can be reused. Increasing pipeline depth can therefore reduce occupancy or force a smaller tile even when it hides more latency.

## Conditions and remaining design space

Small M is common during decode. If output tiling exposes too little work, changing tile order alone will not fill the GPU. Splitting K creates additional work but adds partial-output storage and a reduction. The useful comparison is persistent tiling versus a smaller tile or a split-K design, including the reduction and epilogue.

For large prefill matrices, locality and steady-state pipeline utilization can dominate. For small expert batches, tile costs may differ substantially. Static assignment can strand workers on expensive tiles; dynamic assignment has its own scheduling overhead. Expert-specific grouping belongs in [MoE execution](../moe-execution/README.md).

A persistent kernel also competes with communication for GPU execution resources. Optimizing an isolated GEMM to occupy every SM may lengthen a model iteration when a collective is intended to overlap it.

## Experiment that separates the causes

Preserve the projection's real M/N/K, strides, dtype, and epilogue. Compare equal tile shapes under ordinary, persistent, and grouped scheduling before changing tile size. Record output-tile count, partial waves, shared-memory use, and total time including reduction or conversion. Repeat with a warm weight working set and a model-sized working set that exceeds cache.

Then run the kernel with the model's concurrent communication and return it to the complete layer. If isolated gains disappear, investigate resource contention and changed overlap rather than extending the local tuning sweep indefinitely.

## Sources and implementation state

Checked 2026-10-14. These mechanisms are already implemented upstream.

- [Triton Gluon persistence tutorial](https://triton-lang.org/main/getting-started/tutorials/gluon/persistence.html), including producer/consumer counters and buffer-lifetime discussion.
- [Pinned tutorial implementation](https://github.com/triton-lang/triton/blob/4ee1a827440d453ca276ded4219190d5e7346b8b/python/tutorials/gluon/07-persistence.py), with Hopper and Blackwell paths.
- [CUTLASS efficient GEMM](https://github.com/NVIDIA/cutlass/blob/main/media/docs/cpp/efficient_gemm.md), covering persistent scheduling, epilogues, and split-K. Its Hopper specialization details do not describe Blackwell unchanged.
