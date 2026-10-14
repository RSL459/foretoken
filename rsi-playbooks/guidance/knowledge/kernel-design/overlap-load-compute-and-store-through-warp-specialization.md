<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Overlap load, compute, and store through warp specialization

English | [简体中文](overlap-load-compute-and-store-through-warp-specialization_zh.md)

## Divide responsibilities rather than only data

Ordinary parallel decomposition gives different warps different elements of the same computation. Warp specialization gives them different jobs. One partition loads operands, another issues matrix operations, and another converts and stores completed results. These partitions communicate through shared-memory buffers and barriers.

Triton Gluon and CUTLASS provide warp-specialized implementations. The Gluon tutorial's elementwise example targets Hopper and newer; its `tcgen05` matrix example targets Blackwell. Different devices require different instruction and synchronization designs.

## One pipeline cycle

Consider a ring with three operand slots. The load partition first waits until slot zero is empty, declares the incoming byte count, and starts asynchronous loads. The compute partition waits for the ready phase of slot zero, consumes the operands, and eventually marks it empty. Meanwhile the producer may fill slots one and two. An independent epilogue waits for a completed accumulator, converts it, stages the result in shared memory, and initiates the store.

Barrier phases distinguish successive uses of the same slot. A ready signal from an earlier cycle must not satisfy a later wait. In the tutorial, asynchronous-proxy fences also order generic shared-memory accesses against TMA operations: a barrier between threads is not a substitute for the required proxy ordering.

The steady-state tile interval is bounded by the slowest stage, approximately `max(load, compute, store)` when dependencies and resources permit overlap. Startup, drain, and synchronization remain outside that simplified bound. For a tiny decode matrix, those fixed costs can dominate before a steady state develops.

## Resource allocation is part of the algorithm

Load and store workers need fewer registers than matrix consumers, but the total register and warp allocation can still reduce occupancy. Accumulator double buffering increases overlap while increasing live state. Subtiling an epilogue reduces its shared-memory staging footprint, at the price of more partial operations.

A kernel with additional producer warps can therefore lose even when its timeline shows more overlap. Compare the critical path and output rate, not the number of simultaneous operations. Also test with collectives present: a communication kernel may need the same SMs, memory bandwidth, or shared-memory resources.

The opportunity is to tailor role allocation, buffer depth, accumulator ownership, and epilogue granularity to observed layer shapes. Existing library implementations provide a starting point. The [persistent scheduling entry](reuse-gemm-setup-through-persistent-tile-scheduling.md) covers assignment of multiple output tiles to each worker; specialization addresses the jobs within that worker.

## Distinguishing experiments

Keep arithmetic and tile dimensions fixed while varying one of buffer depth, role allocation, or epilogue subtile size. Include a small decode shape, an intermediate shape, and a sustained prefill shape. Measure registers, spills, shared memory, occupancy, and complete kernel duration. Numerical comparison must include edge tiles and partially filled buffers, where incorrect phase handling or masks often become visible.

Integrate the best candidate with its actual producer and consumer tensors. Check whether conversion or repacking cancels the improvement.

## References

- [Gluon warp-specialization tutorial](https://triton-lang.org/main/getting-started/tutorials/gluon/warp-specialization.html), including barrier phases, proxy fences, and epilogue subtiling.
- [Pinned implementation](https://github.com/triton-lang/triton/blob/4ee1a827440d453ca276ded4219190d5e7346b8b/python/tutorials/gluon/08-warp-specialization.py).
- [CUTLASS GEMM organization](https://github.com/NVIDIA/cutlass/blob/main/media/docs/cpp/efficient_gemm.md), which distinguishes Hopper cooperative and ping-pong designs from Blackwell specialization.
