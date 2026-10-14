<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 量化 MoE 的布局与归约契约

[English](quantized-moe-layouts.md) | 简体中文

## 问题与现状

checkpoint 标注 FP4 或 FP8，不足以确定可执行的 MoE 表示。打包值、scale 粒度与编码、矩阵方向、路由权重应用位置和最终归约，都影响正确性与速度。只关注字节数，可能得到更快但错误的解释。

FlashInfer 已实现 NVFP4、MXFP8、FP8/FP4 DeepGEMM 等量化 fused-MoE 与 EP 路径，当前接口明确区分激活和权重格式。值得研究的是：在支持路径中减少转换与通信成本，同时保持明确的数值契约。

## 执行机制

初始化时准备专家权重与 scale。NVFP4 按 16 个元素分块，MXFP8 按 32 个分块，scale 表示随格式不同。四位值每字节存两个元素，但 scale 和对齐会增加真实字节数。捕获图前，应把权重转换为核函数预期的方向及 scale 布局。

每步按模型原有打分与归一化路由，dispatch 或搬运 hidden states，按需量化激活，执行 FC1 与激活函数，准备 FC2 输入，执行 FC2，最后合并专家输出。dispatch 前量化可能降低通信字节数；dispatch 后量化则可能避免通信后端不支持该格式的问题。二者属于不同的生产者—消费者契约。

核对的 TRT-LLM FP4 接口对 routed GEMM 只接受线性 hidden-state scale 布局，拒绝 swizzled 布局。元素数量正确，不代表 scale 排列正确。门控权重同样需要保持 gate/up 行关系，包括 padding。

归约语义独立于权重量化。BF16 partial 在线上传输、FP32 显式求和再转 BF16，与无序 BF16 原子累加不同；把每个 FC2 partial 量化后传输，则在 FP32 求和前额外引入一次量化往返。FlashInfer 已暴露这些选择，上游调优记录讨论了数值与性能取舍，并没有把它们视作等价实现。

例如两个 partial 为 `a` 和 `-a+delta`，只对接近零的和计算相对误差容易失真，应同时观察各项大小、绝对残差和整层误差。即便实数公式等价，把路由权重乘法移到低精度操作之前，也会改变舍入。

## 适用条件与取舍

当前后端支持矩阵按硬件区分。SM100 系列 NVFP4 路径不能证明 Hopper 原生 FP4 或沐曦支持。W4A16、W4A8、W4A4 在激活精度、带宽、转换工作及累加行为上不同。部分分离式 W4A8 路径要求特征维度按 128 对齐，应核对具体后端，不要扩大为全部 MoE 核函数的限制。

小批量中，权重流量或转换成本必须足够突出，才能偿还打包与 scale 开销。更小的通信 payload 若要求不同的返回调度，也可能变慢。冗余专家迁移时必须连同 scale 一起传输。

## 实验与服务验证

先分离布局正确性和量化质量。使用实际量化操作数，以普通反量化加 FP32 的 MoE 计算对照核函数；再把这些操作数及模型输出与原始高精度 checkpoint 对照。核函数一致不能证明 checkpoint 量化保留了任务质量。

覆盖不均匀与空专家、热点、gate/up 转换、padding 维度及强抵消输出。初始化单独计时，每步量化、dispatch、计算、combine 和输出复制分别观察。条件允许时，用相同有效操作数与通信配置比较 dispatch 前后量化。

部署真实完整模型服务，报告未加 profiler 的 TPOT、TTFT、输出长度与任务分数。加入长上下文和混合负载，因为额外工作区可能减少 KV 容量。

## 依据与剩余问题

核对日期：2026-10-14。FlashInfer [commit a8e747c3](https://github.com/flashinfer-ai/flashinfer/tree/a8e747c3c1f7dfe5d51fab3883824b15da6829b7) 的 [MoE-EP 架构](https://github.com/flashinfer-ai/flashinfer/blob/a8e747c3c1f7dfe5d51fab3883824b15da6829b7/docs/design_docs/moe_ep_architecture.md)、SM100 调优笔记与 [TRT-LLM FP4 接口](https://docs.flashinfer.ai/generated/flashinfer.fused_moe.trtllm_fp4_block_scale_moe.html)。研究空间是目标负载的格式选择、转换位置及数值归因。选择通信格式前参见[小批调度](small-batch-megakernel-scheduling_zh.md)，不要沿用大批量排名。
