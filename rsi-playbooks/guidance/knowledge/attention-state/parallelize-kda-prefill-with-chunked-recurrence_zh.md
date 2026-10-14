<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 用分块循环计算并行执行 KDA 预填充

[English](parallelize-kda-prefill-with-chunked-recurrence.md) | 简体中文

## 问题与当前上游

线性注意力用固定大小的循环矩阵代替持续增长的逐 token 缓存。Decode 为每个活跃请求、每层、每个 token 读取并更新矩阵，状态流量因此成为重要成本。Prefill 一次处理多个 token，需要将相互依赖的更新改写为并行计算。

2025 年 10 月的 Kimi Linear 报告提出 Kimi Delta Attention（KDA），在 Gated DeltaNet（GDN）基础上增加按通道遗忘。Flash Linear Attention（FLA）已提供 chunk 与 fused-recurrent 路径，以及不同后端适配。进一步优化涉及状态流量、布局、数值和不等长序列执行。

## 一个 token 怎样更新状态

采用 key-first 布局，状态 `S` 的形状为 `[K,V]`，`q`、`k`、`v`、`r` 和 `o` 均按列向量表示。归一化 key `k` 和 query `q` 长度为 `K`，value `v` 长度为 `V`，每通道 decay `alpha` 长度为 `K`，更新强度 `beta` 为标量。这里的 `q` 已包含模型的输出缩放：

```text
A  = diag(alpha)
Sd = A*S
r  = v - transpose(Sd)*k
S' = Sd + beta*k*transpose(r)
o  = transpose(S')*q
```

等价地，`S' = (I - beta*k*k^T)*A*S + beta*k*v^T`。更新先减去状态沿当前 key 已经预测出的 value，再写入新 value，避免简单加法记忆在重复 key 上持续累积。

例如两个通道的 `alpha=[0.99,0.10]`，第一行大部分保留，第二行明显遗忘。GDN 的标量 decay 无法在同一个 head 内作这种区分。顺序同样重要：先 decay，再针对衰减后的状态算 residual，最后更新。把对角 decay 移到 `k*k^T` 的另一侧，一般会改变结果。

decode 可以用融合内核为每条活跃序列完成更新与读出。prefill 则把 token 分块：块内累计对角衰减和低秩修正形成依赖，通过三角变换得到辅助矩阵，将块内主要工作改写为并行矩阵乘法；只有块边界状态需要顺序传递。这是在保持模型 recurrence 的前提下，用一些临时计算和存储换取 Tensor Core 友好的执行。

## 适用条件与取舍

KDA 是训练得到的模型结构，不是把普通 transformer 切成线性注意力的运行开关。Kimi Linear 每三层 KDA 后安排一层全局 MLA，周期性保留显式历史注意力。因此总模型状态并非与上下文长度无关：MLA 缓存仍会增长。

引用版本的 FLA chunk API 接受 32 或 64 的 chunk size，key dimension 最大为 256；显式提供的 initial state 必须为 FP32，激活通常使用 BF16。log-space gate、在内核中转换的 raw gate、经过 sigmoid 的 beta 是不同输入约定，混用会直接改变遗忘强度。

默认 final state 布局为 `[N,HV,K,V]`，也有 value-first 选项；不等长打包通过 `cu_seqlens` 表达。公开 fused-recurrent wrapper 没有暴露底层所有 state-index 与 accepted-token 参数。引擎适配层不能因为公开函数存在，就认为 continuous batching 的 slot 生命周期已经被它处理。CUDA 和 Ascend 有后端，也不代表功能或性能完全一致。

## 实现入口与剩余设计空间

同时阅读 FLA chunk、fused-recurrent API 和模型 gate 生成路径。先确定 query/key head 共享关系、value head 数、归一化、布局以及 final state 由谁持有，再改内核。

可研究状态布局能否同时适合 decode 读出与 chunk 边界交接；低 batch 下 gate 与归一化融合能否减少 launch；形状专用 chunk 调度能否降低不等长 prefill 的 padding 工作。应复用现有后端。若高 batch 的主要成本是循环矩阵写回，[基于 replay 的状态表示](reduce-recurrent-state-writes-with-replay-buffers_zh.md)处理的是另一机制，不能把标量 decay 的 GDN replay 原样认作 KDA 通道 decay 支持。

## 从局部到服务的实验

对同一 token 流固定 initial state、gate、归一化和输出 scale，比较 chunk 与 recurrent 的结果。必须将 prefill 生成的 final state 接入 decode；两边都从零开始时，布局错误可能被隐藏。输入覆盖重复 key、差异很大的通道 decay、长序列、无效 padding slot 与不等长打包。

短 decode 与长 prefill 分开剖析，记录状态字节流量、寄存器占用、chunk 临时存储和无效 slot 的工作，不能只看 token 吞吐。然后在真实 hybrid 模型上扫描上下文与并发，拆分 KDA、MLA 和 MoE 时间，检查长上下文检索、续写质量，以及复用请求 slot 时是否残留上一请求状态。结合 KDA 的实测耗时占比解释数值与服务结果。

## 参考

- [Kimi Linear，2025-10-30，v1](https://arxiv.org/html/2510.26692v1)：KDA recurrence、对角加低秩的分块执行和 hybrid 结构。
- [FLA chunk API，固定 `1fe52b5d05c53601885610fab3d39157647d836d`](https://github.com/fla-org/flash-linear-attention/blob/1fe52b5d05c53601885610fab3d39157647d836d/fla/ops/kda/chunk.py)：gate 输入、状态精度、打包和 chunk 限制。
- [同一 revision 的 fused-recurrent 实现](https://github.com/fla-org/flash-linear-attention/blob/1fe52b5d05c53601885610fab3d39157647d836d/fla/ops/kda/fused_recurrent.py)：更新顺序、状态布局、公开接口与底层接口的区别。
