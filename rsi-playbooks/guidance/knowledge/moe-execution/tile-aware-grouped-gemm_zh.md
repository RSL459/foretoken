<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 减少 token 物化开销的分组 GEMM

[English](tile-aware-grouped-gemm.md) | 简体中文

## 问题与现状

稀疏专家混合（MoE）层的计算量降低，不代表执行时间同步下降。专家中间维度越小，收集输入、写出中间结果和合并专家输出的开销越突出。只优化矩阵乘法，可能没有触及真正的瓶颈。

SonicMoE 已实现融合输入收集的 grouped GEMM 和激活融合。论文主要评估训练，包含反向传播的激活保存；这部分显存节省不能算作 decode 收益。它的 token rounding 会改变 token 选中的专家，属于训练与硬件协同设计，不是现有推理路由的无损替代。推理侧值得复用的问题是：保持原始路由，怎样更高效地执行它？

## 执行机制

输入 `X[T,H]` 包含 `T` 个 token，每个 token 的 hidden width 为 `H`，选择 `K` 个逻辑专家。专家 `e` 接收 `m_e` 行；所有路由有效时，`sum(m_e)=T*K`。用 `row_e(t)` 表示原 token `t` 在专家 `e` 中的局部行号。带门控的前馈计算依次为：

```text
H_e = gather(X, token_indices_e) @ W1_e
A_e = SwiGLU(H_e)
Y_e = A_e @ W2_e
y_t = sum_{e selected by t} routing_weight[t,e] * Y_e[row_e(t)]
```

第一个分组矩阵乘法的行数 `M=m_e` 随专家变化，特征维度固定。SonicMoE 根据路由索引直接把输入行加载到共享内存，不先把完整收集结果写入 HBM；SwiGLU 融合在第一个 GEMM 的收尾阶段。第二个 GEMM 连续写出各专家结果，再由 gather-and-sum 核函数恢复 token 顺序并应用路由权重。

最后两步分开并非遗漏融合。Hopper 上分散的全局内存写入可能妨碍收尾 I/O 与下一块矩阵乘法重叠。连续异步写出再单独归约，有时优于“少一个核函数”的方案。融合应消除昂贵的数据流，而不是只追求启动次数少。

例如三个专家分别收到 `[1,17,129]` 行，行 tile 为 128：有效工作为 147 行，tile 容量却是 `128+128+256=512` 行。这只是形状示例，不是实测慢了多少倍；掩码加载、Tensor Core 指令和权重复用的成本并不相同。比较小 tile、收集融合和分组调度时，应保留全部 147 条真实路由，不能靠删掉 token 美化利用率。

## 适用条件与取舍

核对的实现通过 CuTeDSL、QuACK 和 Triton 支持 NVIDIA Hopper 与 Blackwell 系列。Hopper 的 warpgroup 交替执行、Blackwell 的 tensor memory 分阶段使用，是 I/O 与矩阵乘法重叠的不同硬件实现，不能直接推断沐曦或 AMD 上也成立。

隔离执行优化时，保持 BF16 输入、激活函数、路由归一化和权重布局一致。仓库区分 gate/up 交错布局与 checkpoint 的拼接布局，转换错误可能同时带来更短执行时间和错误输出。如果 EP 通信已经返回连续专家布局，再做本地收集优化可能没有多少可消除的工作。

## 区分原因的实验

重放真实层的激活和路由，再构造有效路由总数相同的均匀分布、热点集中分布和大量单行专家。token 数从单请求 decode 扫到 prefill 批量。计时范围覆盖路由到最终归约，不能只测 GEMM。

记录有效行数、tile 容量、收集流量、两次 GEMM、归约、启动间隙和工作区峰值。如果优化只在 EP dispatch 之前有效，原因是本地物化减少，而不是 GEMM 普遍变快。连续输出即使多一个核函数仍更快时，应检查异步写出重叠及归约流量。

逐层与原始实现和路由对照，再在真实服务运行完整模型。分别测并发一和持续并发下未加 profiler 的 TPOT、TTFT、输出长度与回答质量。

## 依据与剩余问题

核对日期：2026-10-14。[SonicMoE 论文](https://arxiv.org/abs/2512.14080)的算法 1–4、第 3–5 节与附录 B/F，以及 [commit 7396f3e](https://github.com/Dao-AILab/sonic-moe/tree/7396f3e604827d8186c2e16e64b28ee33d3defd0) 的 `sonicmoe/functional/forward.py`、`benchmarks/moe-cute.py`。剩余工作是针对目标引擎实际 dispatch 布局与小批形状做集成和测量；通信决定输入布局时，参见[并行与通信](../parallelism-communication/README_zh.md)。
