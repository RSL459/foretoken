<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 异构执行

[English](README.md) | 简体中文

按执行机制比较硬件，不按厂商罗列功能。这些条目研究设备内计算、内存搬运与通信约束，不承担集群调度和部署职责。

- GEMM 参数不再适合新代际或新 batch：[CDNA 形状、布局与矩阵吞吐](cdna-shapes-and-layouts_zh.md)。
- CUDA 风格接口不能保证相同量化融合：[MetaX 量化阶段边界](metax-native-quantized-fusion_zh.md)。
- 图重放和辅助流改变延迟或执行进展：[图与 stream 的跨 backend 约束](graph-stream-portability_zh.md)。
- 通信更快但模型没有加速：[关键路径上的 collective](collective-critical-path_zh.md)。
- 判断 offload 和不同性能设备是否有帮助：[CPU/GPU 放置与传输预算](cpu-gpu-placement_zh.md)。

其他机制分别见[量化](../quantization/README_zh.md)、[kernel 设计](../kernel-design/README_zh.md)、[编译与 runtime](../compiler-runtime/README_zh.md)、[并行与通信](../parallelism-communication/README_zh.md)。返回[知识索引](../README_zh.md)。

## 资料范围

官方文档和当前源码核对日期为 2026-10-14。快照为 vLLM `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`、AITER `c09dc31787c21cd7fa7acbe4addef256766bd58a`、ROCm systems `f1b316f12c75430787032e99405834f59a026ae1`、MetaX vLLM `cec91763dbe968fe4478fc066f57ecf5877c3965`、llama.cpp `77c4540ce4667f4577753fe034a3a8042f510b8f`，均提交于 2026-10-13。MetaX mcoplib head `f325795aac1ee71cd51111b065f6dd175246961d` 提交于 2026-10-08。源码中存在能力，不等于不同发行版二进制可以任意组合。
