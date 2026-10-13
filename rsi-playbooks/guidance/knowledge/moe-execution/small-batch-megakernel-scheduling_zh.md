<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 小批 MoE 需要不同的 GPU 工作划分

[English](small-batch-megakernel-scheduling.md) | 简体中文

## 问题与现状

单请求 decode 可能激活多个专家，却只给每个专家一行输入。大批量 grouped GEMM 配置这时可能主要忙于加载权重和协调执行单元。分开的通信与计算带来启动边界；megakernel 将它们融合后，又需要在一个持久核函数中固定分配 GPU 资源。

FlashInfer 已提供分开的 dispatch/compute/combine 和融合的 MegaMoE 后端，也已有按架构、dtype 区分的配置、离线调优和容量工作区。值得研究的是为实际有效 token 数选择合适工作划分，并证明它在哪些负载下优于现有路径。

## 执行机制

分离式 MoE 先通信形成专家输入，再执行本地两次投影，最后把结果返回源 rank。megakernel 在一次执行中包含通信与专家计算，由不同 warp 承担输入搬运、矩阵乘法、收尾和结果返回。这些角色争用 SM、寄存器、共享内存及带宽。

每个专家行数 `m_e` 很小时，更宽的输出特征 tile 可能增加无效工作或延长资源占用；增加通信执行单元可以缩短到达等待，却会挤占专家计算。核对的 FlashInfer SM100 NVFP4 配置针对不同容量，改变输出 tile 宽度以及结果返回角色：由收尾 warp、复用的 dispatch warp 或独立 warp 完成。这些已经实现，配置分界是具体形状下的经验结果，不是通用阈值。

必须区分容量 `C` 与有效 token 数 `T`。容量为 `C=2048` 的工作区可能每步只运行 `T=8`。容量决定存储及部分编译选择，有效工作量决定真实计算和路由。只按满容量调优，可能为低负载选择错误配置。当前架构文档已有按有效 token 记录离线结果和预建工作区的流程，调优笔记较旧章节仍描述仅按容量选择。应核对目标版本实际走哪条路径，不能假设所有说明已经同步。

## 适用条件与取舍

来源中的实现针对 NVIDIA，不同 SM90、SM100 系列及其他后端有独立路径。比较时固定支持的架构与量化格式，BF16、NVFP4、MXFP8 不属于数值等价的性能排名。

小批 decode 即便融合通信，仍可能受限于权重带宽；融合不能凭空增加 token 间权重复用。大批量则可能受益于更激进的计算划分。上游调优记录明确存在 combine 量化和核内归约在小批量变慢、在大批量有利的情况。

工作区配置不是并发隔离通道，池化存储必须保持 stream 顺序。先创建、预热，再捕获图；相关图退役之前保留存储。需要所有 rank 同步编译和计时的调优不能放进服务请求路径。

## 区分假设与服务验证

固定容量，扫描有效 token `1,8,64,512` 和更满的批量；再固定有效 token，增加容量，以区分调度与缓冲区大小的影响。覆盖均匀路由、单热点专家和各 rank 到达不齐的情况，记录实际专家行数，而不是只记录客户端并发。

分别测输入量化、搬运、核函数、输出复制和最慢 rank 完成时间。上游预先准备输入的微基准不包含每步激活准备成本：复现其计时范围用于对照，再把遗漏工作纳入服务分析。检查候选到底减少启动间隙、缩短 GEMM，还是只改变了跨 rank 启动偏斜。

先核对路由与数值，再部署完整模型。测并发一 TPOT 和流量波动时开放环请求延迟，明确图覆盖与质量条件。只改善饱和吞吐却恶化低负载 decode 的配置，应是特定负载选项，不是无条件默认值。

## 依据与剩余问题

核对日期：2026-10-14。FlashInfer [MoE-EP 架构](https://github.com/flashinfer-ai/flashinfer/blob/a8e747c3c1f7dfe5d51fab3883824b15da6829b7/docs/design_docs/moe_ep_architecture.md)及 [SM100 调优笔记](https://github.com/flashinfer-ai/flashinfer/blob/a8e747c3c1f7dfe5d51fab3883824b15da6829b7/flashinfer/moe_ep/kernel_src/sm100/cutedsl_megamoe/TUNING.md)，commit `a8e747c3`。剩余问题是确认目标引擎当前配置选择路径并评估低负载表现。本地 I/O 见[分组 GEMM](tile-aware-grouped-gemm_zh.md)，SM 争用见[通信重叠](../parallelism-communication/low-latency-dispatch-overlap_zh.md)。
