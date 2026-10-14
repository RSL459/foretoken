<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 动态形状与有收益的专门化

[English](dynamic-shape-specialization.md) | 简体中文

服务批次变化可能导致反复编译，通用符号内核又可能在常见形状上偏慢。专门化以启动成本换取稳态执行收益。

## 符号编译与图重放解决不同问题

符号化编译产物可以接收变化的维度而无需重新编译，但 CUDA Graph 通常仍要求固定的捕获执行形状。因此一个 Inductor 符号图可能对应多个 CUDA Graph 记录。混淆两种缓存，就难以判断时间耗在生成代码、捕获图，还是补齐后的计算。

PyTorch v2.14 的自动动态行为是：初次按静态尺寸编译，尺寸变化触发重编译后，变化的维度可以转为动态。显式标注输入可避免第一次不必要的专门化；文档推荐定向标注，而非把所有尺寸和整数都设为动态。

vLLM 已有独立的编译集成及可选静态 `compile_sizes`。应先检查这些已有入口，而不是再把完整 serving 应用包进另一层 `torch.compile`。

## 为什么动态输入仍会产生专门化

假设代码针对 token 数为一、小于某阈值和超过阈值采用不同操作。符号执行会沿当前分支追踪，并保留该路径成立的条件。后续形状跨过条件时，仍可能需要另一个图。动态维度不会消除算法本身的分支。

类似情况也发生在 Triton 把变化值当作 `constexpr`，或自定义算子的元数据实现将符号维度转成具体整数时。仅标注外层张量动态，不能解决内部的专门化边界。

设计时应区分频繁变化的 token 数与稳定的 head size、矩阵宽度。稳定参数有利于专门化；变化维度可以使用符号代码、少量常见静态版本，或 graph padding 桶。这些选择把成本分配给启动、代码质量、补齐计算和内存。

## 判断专门化是否值得

设某形状新增编译／捕获成本为 `C`，相对通用路径每次节省 `Δt`，当 `Δt > 0` 且暂不考虑内存与争用时，执行 `ceil(C/Δt)` 次可摊平准备成本。频率应来自 worker 生命周期内真实的 engine step，而不是不断重复同一个形状的微基准。

还需区分有意的按形状选算法与偶然产生的 guard。删除有意义的分支可能损害快路径；反过来，等价布局选择上的 Python 分支又可能产生不必要的图版本。应依据 guard 和生成代码定位，而非一律追求单一图。

## 实验方式

在新进程和已预热进程中重放代表性的批次形状序列，记录编译事件、图捕获、产物版本、内存与 step 时长。比较通用路径与少量高频静态形状，尽量保持算子和后端选择一致。

输入覆盖阈值两侧、支持的空或单元素维度及任务最大形状，用编译器 guard 诊断和生成内核定位专门化。部署就绪时间与稳态服务表现分别测量：短生命周期 worker 与长期副本可能适合不同策略。

## 来源与实现状态

核对日期：2026-10-14。

- [PyTorch v2.14 动态形状文档](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_dynamic_shapes.md)：自动动态、定向标注与专门化语义。
- [vLLM v0.31.0 编译集成](https://docs.vllm.ai/en/v0.31.0/design/torch_compile/)：符号 token 维度、静态编译尺寸和产物复用。
- [PyTorch v2.14 CUDA Graph Trees](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md)：按具体执行形状分别记录；相关设计见[图分桶](graph-buckets-and-dispatch_zh.md)。
