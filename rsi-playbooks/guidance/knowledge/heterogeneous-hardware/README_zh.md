<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 异构执行

[English](README.md) | 简体中文

设备指令布局、内存搬运、stream 依赖与 collective 实现，决定同一模型在不同硬件上的执行方式。

- GEMM 参数不再适合新代际或新 batch：[CDNA 形状、布局与矩阵吞吐](cdna-shapes-and-layouts_zh.md)。
- CUDA 风格接口不能保证相同量化融合：[MetaX 量化阶段边界](metax-native-quantized-fusion_zh.md)。
- 图重放和辅助流改变延迟或执行进展：[图与 stream 的跨 backend 约束](graph-stream-portability_zh.md)。
- 通信更快但模型没有加速：[关键路径上的 collective](collective-critical-path_zh.md)。
- 判断 offload 和不同性能设备是否有帮助：[CPU/GPU 放置与传输预算](cpu-gpu-placement_zh.md)。

其他机制分别见[量化](../quantization/README_zh.md)、[kernel 设计](../kernel-design/README_zh.md)、[编译与 runtime](../compiler-runtime/README_zh.md)、[并行与通信](../parallelism-communication/README_zh.md)。返回[知识索引](../README_zh.md)。
