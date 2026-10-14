<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Heterogeneous execution

English | [简体中文](README_zh.md)

Device instruction layouts, memory movement, stream dependencies, and collective implementations determine how the same model executes on different hardware.

- GEMM tuning stops fitting another AMD generation or batch: [Improve CDNA GEMM: Shape-Aware Tiles and Layouts](improve-cdna-gemm-shape-aware-tiles-and-layouts.md).
- CUDA-like APIs do not preserve quantized fusion: [Reduce MetaX INT8 Traffic Through Compatible Stage Fusion](reduce-metax-int8-traffic-through-compatible-stage-fusion.md).
- Graph replay and auxiliary streams change latency or progress: [Reduce Launch Overhead: Backend-Aware Graphs and Streams](reduce-launch-overhead-backend-aware-graphs-and-streams.md).
- Faster communication does not accelerate the model: [Reduce Collective Delays: Backend-Specific Algorithms and Compute Overlap](reduce-collective-delays-backend-algorithms-and-compute-overlap.md).
- Decide when offload or unequal devices help: [Balance Capacity and Latency Through CPU/GPU Placement](balance-capacity-and-latency-through-cpu-gpu-placement.md).

See [quantization](../quantization/README.md), [kernel design](../kernel-design/README.md), [compiler/runtime](../compiler-runtime/README.md), and [parallelism/communication](../parallelism-communication/README.md) for their respective mechanisms. Return to the [knowledge index](../README.md).
