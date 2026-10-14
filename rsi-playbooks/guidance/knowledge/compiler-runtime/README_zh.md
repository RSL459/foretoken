<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 编译与运行时

[English](README.md) | 简体中文

理解形状选择、编译器可见性和内存归属，如何把独立内核组织成反复执行的推理过程。

- [按实际负载分桶捕获图，减少启动开销](reduce-launch-overhead-with-workload-aware-graph-bucketing_zh.md)：提高重放覆盖率，同时控制 padding、捕获时间和内存。
- [选择高频形状专门化，权衡编译成本与执行收益](balance-compilation-cost-with-targeted-shape-specialization_zh.md)：决定哪些维度保持符号化，哪些高频形状值得生成专用代码。
- [权衡自定义内核控制与编译器可见融合](balance-custom-kernels-and-compiler-visible-fusion_zh.md)：保持元数据、mutation 和捕获语义，选择编译器可优化的范围。
- [按张量生命周期共享图内存池，保留跨步状态](reuse-graph-memory-through-lifetime-aware-pooling_zh.md)：跨路径复用内存池和输出，同时保留状态与服务容量。

内核内部工作见[算子设计](../kernel-design/README_zh.md)，外围提交与流式链路见[主机执行](../host-streaming/README_zh.md)。

[全部推理知识](../README_zh.md)
