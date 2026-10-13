<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 编译与运行时

[English](README.md) | 简体中文

理解形状选择、编译器可见性和内存归属，如何把独立内核组织成反复执行的推理过程。

- [图分桶与运行时分派](graph-buckets-and-dispatch_zh.md)：提高重放覆盖率，同时控制 padding、捕获时间和内存。
- [动态形状与专门化](dynamic-shape-specialization_zh.md)：决定哪些维度保持符号化，哪些高频形状值得生成专用代码。
- [自定义算子边界](custom-operator-boundaries_zh.md)：保持元数据、mutation 和捕获语义，选择编译器可优化的范围。
- [图内存生命周期](graph-memory-lifetimes_zh.md)：跨路径复用内存池和输出，同时保留状态与服务容量。

内核内部工作见[算子设计](../kernel-design/README_zh.md)，外围提交与流式链路见[主机执行](../host-streaming/README_zh.md)。

[全部推理知识](../README_zh.md)
