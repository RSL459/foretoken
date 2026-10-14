<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 按形状调整分块与布局，提高 CDNA 矩阵执行效率

[English](improve-cdna-gemm-shape-aware-tiles-and-layouts.md) | 简体中文

针对大 prefill batch 调好的矩阵 kernel，遇到 decode 或稀疏专家时可能效率很低。AMD CDNA 上应按矩阵指令、wavefront、片上共享内存（LDS）和 scale 布局分析，而不是复制其他 GPU 代际的 launch 参数。

## 从 tile 追踪执行

`X[M,K] W[K,N]` 的计算量为 `2MKN`，每个输入只读一次、输出只写一次时，最小逻辑流量为 `bytes(X)+bytes(W)+bytes(Y)`；分块重读、scale 读取和寄存器溢出会增加流量。小 M 时读取许多权重只服务少量 token；大 M 时一份权重 tile 可被更多行复用。`min(计算上限, 带宽 × 算术强度)` 可以解释瓶颈转移，但没有包含 launch、寄存器溢出和 tile 利用率。

CDNA 分块 kernel 从 HBM 读取操作数，在 LDS 或寄存器中暂存，再送入矩阵融合乘加（MFMA）指令、累加并完成输出处理。lane 到元素的映射必须匹配指令和 dtype。64 线程 wavefront 不能原样执行面向 32 线程 CUDA warp 的布局。更大 tile 增加复用，也增加寄存器和 LDS 占用；M 很小时可能只有少量 block 可调度。

当前 AMD 架构表中，CDNA3 `gfx942` 的 MI300X/MI325X 为 64 线程 wavefront、64 KiB LDS；CDNA4 `gfx950` 的 MI350X/MI355X 为相同 wavefront 宽度、160 KiB LDS。LDS 更大扩展了 staging 选择，但不是“大 tile 一定更快”，仍受 occupancy、单 block 分配和指令支持约束。

例如 `M=4` 的投影使用按 `M=128` 设计的 tile，会浪费多数行。skinny GEMM 或 split-K 可暴露更多并行任务，不过 split-K 增加部分结果归约和流量，大 M 时可能不如普通 GEMM。MoE 还要看每个专家收到多少 token；总 batch 很大，仍可能包含许多微小专家 GEMM。

## 当前上游已有实现

AMD 的 vLLM 指南已经说明 AITER linear、skinny GEMM、hipBLASLt、FP8 padding 和 CDNA4 FP4 assembly GEMM。FP4 assembly 路径要求 MI350X/MI355X 与 MXFP4 权重。AITER 提供算子、模型／架构 tuning 配置和 GEMM/MoE 测量入口。

引用版本的 vLLM MXFP4 源码包含 backend 格式转换，以及显式 gfx942 groupwise-int4 转换路径。它与 CDNA4 原生 MXFP4 算术是不同执行表示，仅按“四位权重”比较会掩盖转换和 kernel 差异。

剩余空间包括生产形状未覆盖、权重与 scale 布局不匹配、padding 浪费，以及现有 kernel 的更合适选择。BF16、FP16、FP8、MXFP4 要分别建立形状结论；某个架构、专家宽度或量化分组的调优不能成为通用 ROCm 默认。

## 从形状收益走到服务收益

复用 AITER 的 `op_tests/test_gemm_a8w8.py` 和 `test_moe.py`，按实际模型形状构造输入，沿用库本身的测量方法。比较当前 kernel 与另一受支持 schedule，检查指令利用、LDS／寄存器压力、spills、launch 数、padding 和输出误差。专家输入应包含不均匀 token 分布，不只测均匀合成 batch。

比较低负载 decode 和 prefill/decode 混合服务，两者会暴露不同的 M 分布，以及与 attention、collective 的资源争用。

## 参考

- [AMD 架构规格](https://rocm.docs.amd.com/en/latest/reference/gpu-arch-specs.html)。
- [当前 vLLM/AITER 优化指南](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/optimization/vllm-v1-optimization.html)。
- [固定 commit 的 AITER](https://github.com/ROCm/aiter/tree/c09dc31787c21cd7fa7acbe4addef256766bd58a)。
- [vLLM MXFP4 布局与转换](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/layers/quantization/mxfp4.py)。

[异构执行](README_zh.md) · [Kernel 设计](../kernel-design/README_zh.md) · [知识索引](../README_zh.md)
