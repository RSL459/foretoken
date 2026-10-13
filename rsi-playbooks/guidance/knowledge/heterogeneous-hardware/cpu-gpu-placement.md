<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# CPU/GPU placement and transfer budgets

English | [简体中文](cpu-gpu-placement_zh.md)

Adding memory capacity can make a model runnable without making it fast. CPU/GPU offload and unequal accelerators require a computation-and-transfer budget. The right placement depends on whether layers execute sequentially, tensor shards synchronize inside every layer, or weights are transferred for each forward pass.

## Capacity and latency are different constraints

For device j, feasibility requires

```text
weights_j + state_j + workspace_j + graph_memory_j ≤ usable_memory_j.
```

This says nothing about how long a request takes. A sequential layer partition has approximately the sum of each partition's compute time plus activation transfers. A tensor-parallel layer is instead constrained by the slowest participating shard plus reduction/communication. Memory-proportional splitting is therefore a capacity heuristic, not a guarantee of balanced compute.

Suppose two devices have equal available memory but one processes the relevant GEMM twice as fast. An equal tensor split can leave the faster device waiting. A throughput-balanced split might give it more work, but alignment, model architecture, kernel support, and repeated reductions still constrain the assignment. For sequential layer placement, assigning more layers to the faster device may improve latency even when total memory fits either split.

Weight offload has a different cost. If S bytes must cross the CPU/GPU link on each token and sustained bandwidth is B, transfer time alone is at least `S/B`. Streaming 4 GiB at an illustrative 32 GiB/s takes 125 ms before compute or synchronization. This is a dimensional example, not a measured link rate. Transferring only activations at a partition boundary can be far smaller; CPU-resident layers instead pay CPU weight reads and matrix execution. These mechanisms should not all be called “offload” without explaining which one runs.

## Current implementations supply placement primitives

The checked llama.cpp multi-GPU guide already supports layer placement, GPU-layer limits, and split proportions. Layer mode assigns contiguous layers and minimizes cross-device transfers. Its experimental tensor mode splits weights/state and performs repeated cross-GPU reductions; the guide emphasizes NVIDIA CUDA performance and does not guarantee equivalent results on other backends. Tensor mode requires supported architectures and flash attention, currently excludes quantized cache types, and lacks automatic fitting. Deprecated row mode is not a new candidate.

The same guide records a useful real backend difference: NCCL support is enabled by default at build time when available, while HIP RCCL support is disabled by default because it was not universally beneficial in upstream testing. These defaults are evidence of different execution trade-offs, not a rule to turn RCCL off in unrelated engines.

For CPU execution, current vLLM documentation recommends NUMA-local rank memory and threads, reserving host cores for serving, and avoiding hyperthread oversubscription. BF16/FP16/FP32 support and instruction eligibility vary by architecture. A CPU backend's matrix instructions do not imply a GPU-offload path or a common quantized format.

## Remaining choices and discriminating experiments

The useful remaining space is placement that matches measured compute, memory bandwidth, NUMA locality, and transfer paths. Quantized weights can reduce transfer volume, but conversion and unsupported mixed-backend operators may erase the gain. Cluster scheduling belongs to a separate owner; this note concerns execution inside a chosen device set.

Compare an existing single-device path, layer partition, and supported tensor split using one model and dtype. Measure actual device assignment, per-partition time, transfer volume, reduction time, CPU bandwidth, and NUMA placement. Distinguish model loading from steady-state inference. If offloading weights, include every repeated transfer rather than only a cached warmup.

At service level, measure single-request TPOT, prefill TTFT, throughput under batching, and successful outputs at the target context length. Track host-memory pressure and tail latency when multiple requests share CPU bandwidth. A slower configuration can still be useful because it enables a larger model, but report that as a capacity trade-off rather than a speedup.
## Sources

Checked 2026-10-14.

- [llama.cpp multi-GPU execution at commit 77c4540ce4667f4577753fe034a3a8042f510b8f](https://github.com/ggml-org/llama.cpp/blob/77c4540ce4667f4577753fe034a3a8042f510b8f/docs/multi-gpu.md).
- [Current vLLM CPU ISA, dtype, NUMA, and threading guidance](https://docs.vllm.ai/en/latest/getting_started/installation/cpu/).
- [llama.cpp token-generation performance entry point](https://github.com/ggml-org/llama.cpp/blob/77c4540ce4667f4577753fe034a3a8042f510b8f/docs/development/token_generation_performance_tips.md); its example measurements are historical, not current hardware comparisons.

[Heterogeneous execution](README.md) · [Parallelism/communication](../parallelism-communication/README.md) · [Knowledge index](../README.md)
