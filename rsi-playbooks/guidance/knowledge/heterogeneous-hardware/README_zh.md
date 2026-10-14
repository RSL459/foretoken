<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 异构执行

[English](README.md) | 简体中文

设备指令布局、内存搬运、stream 依赖与 collective 实现，决定同一模型在不同硬件上的执行方式。

- GEMM 参数不再适合新代际或新 batch：[按形状调整分块与布局，提高 CDNA 矩阵执行效率](improve-cdna-gemm-shape-aware-tiles-and-layouts_zh.md)。
- CUDA 风格接口不能保证相同量化融合：[通过兼容布局的量化阶段融合减少 MetaX INT8 中间访存](reduce-metax-int8-traffic-through-compatible-stage-fusion_zh.md)。
- 图重放和辅助流改变延迟或执行进展：[减少启动开销：适配后端的图重放与流依赖](reduce-launch-overhead-backend-aware-graphs-and-streams_zh.md)。
- 通信更快但模型没有加速：[减少 Collective 延迟：后端算法选择与计算重叠](reduce-collective-delays-backend-algorithms-and-compute-overlap_zh.md)。
- 判断 offload 和不同性能设备是否有帮助：[通过 CPU/GPU 放置与卸载平衡容量和延迟](balance-capacity-and-latency-through-cpu-gpu-placement_zh.md)。

其他机制分别见[量化](../quantization/README_zh.md)、[kernel 设计](../kernel-design/README_zh.md)、[编译与 runtime](../compiler-runtime/README_zh.md)、[并行与通信](../parallelism-communication/README_zh.md)。返回[知识索引](../README_zh.md)。
