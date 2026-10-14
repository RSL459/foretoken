<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 算子设计

[English](README.md) | 简体中文

从完整层仍然昂贵的工作选择机制，同时考虑实际输入、输出与并行执行的其他操作。

- [用持久化分块调度复用 GEMM 准备工作](reuse-gemm-setup-through-persistent-tile-scheduling_zh.md)：连续处理多个输出块时，权衡尾浪、局部性与交叠。
- [按 warp 职责分工，重叠加载、计算与写回](overlap-load-compute-and-store-through-warp-specialization_zh.md)：分离加载、矩阵计算与输出职责，控制缓冲和同步对驻留度的影响。
- [按上下游布局融合算子，减少中间访存](reduce-intermediate-traffic-through-layout-aware-operator-fusion_zh.md)：减少中间访存，同时保留消费者、别名与编译器匹配语义。
- [融合基数选择与采样，减少全词表处理](reduce-sampling-work-through-fused-radix-selection_zh.md)：减少过滤和采样工作，保持请求所要求的分布。

模型特定计算见[注意力](../attention-state/README_zh.md)和 [MoE](../moe-execution/README_zh.md)。图集成见[编译与运行时](../compiler-runtime/README_zh.md)，后端特定约束见[异构硬件](../heterogeneous-hardware/README_zh.md)。

[全部推理知识](../README_zh.md)
