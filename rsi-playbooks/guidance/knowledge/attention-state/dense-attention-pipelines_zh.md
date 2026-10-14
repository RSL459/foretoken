<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 非对称 GPU 上的稠密注意力流水线

[English](dense-attention-pipelines.md) | 简体中文

## 问题与当前上游

Tensor Core 的提升不会等比例加速注意力中的所有工作。长上下文 prefill 的矩阵乘法足够快之后，指数运算、行归约、概率转换和输出重缩放可能成为主要成本。单纯扩大 GEMM tile 还可能增加寄存器压力，把瓶颈推向共享内存。

2026 年 3 月的 FlashAttention-4 用 Blackwell 异步流水线应对这种硬件能力不均衡，上游 CuTe-DSL 已提供实现。值得继续研究的是目标模型的形状和服务批次能否有效走到这些路径，以及外围工作是否吞掉了收益。

## 流水线怎样执行

对一个 query tile，内核依次读取 key/value tile，不生成完整的分数矩阵。行最大值、分母和未归一化输出分别初始化为 `m=-infinity`、`l=0`、`O=0`。新 tile 的分数 `S` 已包含 attention scale 与 mask：

```text
m' = max(m, rowmax(S))
a  = exp(m - m')
P  = exp(S - m')
l' = a*l + rowsum(P)
O' = a*O + P*V
最终输出 = O/l
```

`l` 和 `O` 必须一起重缩放。例如最后一个 key tile 才出现最大的 logit，如果只更新新 tile 而不修正旧累计值，早先 token 的权重就会偏大。在线执行避免了平方规模的分数存储，同时保留稠密注意力的语义；具体数值仍受浮点计算影响。

Blackwell 的异步 MMA 把中间结果写入 Tensor Memory。FlashAttention-4 交错处理两个 query tile：Tensor Core 计算其中一个，softmax warpgroup 处理另一个。独立的 correction warpgroup 修正累计输出，让向量重缩放不占据 softmax 主路径。更大的 tile 可以摊薄调度与行统计成本，但必须有足够的并行工作填满流水线。

论文还将部分指数运算交给多项式和 FMA，把工作从专用特殊函数单元转移到其他可用资源。只有这些资源确实闲置时，转移才有意义。条件重缩放允许归一化参考值暂时落后于较小的最大值增长，以减少向量修正；它要求分母、概率与累计输出使用一致的参考值，不能理解成随意丢弃归一化更新。即使不删除任何 token，指数近似和激活值舍入仍需要数值验证。

## 适用条件与取舍

FlashAttention-4 的这条快速路径面向 Blackwell CUDA GPU。Hopper 或其他加速器需要匹配各自架构的实现，不能直接复制线程配置。固定版本接口中，SM100/SM110 forward 接受 FP16、BF16 和指定 FP8 格式，同时明确限制 head dimension；FP8 输出为 BF16，descale 也有独立形状要求。BF16 的 128 维 head 不能代表 absorbed MLA 或 FP8 路径。

短 query、小 batch、不等长序列、GQA 打包、分页缓存、因果 mask 和 split-KV 都可能改变调度选择。两 CTA 协作对大 tile 有利，但当独立 query block 已经很多时也可能浪费资源。更快的 prefill 还可能更集中地争抢 GPU，使并发 decode 受影响；孤立内核吞吐不能直接证明服务延迟改善。

## 实现入口与剩余设计空间

从固定版本 CuTe 接口追踪到 `FlashAttentionForwardSm100`，确认实际选中的 tile、Q staging、split 数和单/双 CTA 路径。上游已有这些实现。论文提到 cuDNN 9.13 起吸收了相关技术，但这不代表所有推理引擎和模型都已调到 FlashAttention-4。

有价值的问题包括形状感知调度、不等长 batch 的负载平衡，以及注意力前后的格式转换。例如扩大 key tile 是否降低了 softmax 成本，却让一个特别长的请求成为尾部拖延？引擎是否把内核省下的时间花在元数据准备上？这些问题分别属于算子或引擎适配层，不应在服务层再建一套注意力实现。

## 从局部到服务的实验

先固定 Q/K/V、mask、scale、dtype 和输出误差要求，对比实际支持的实现。query 长度与 key 长度要分开扫描：完整 prefill、短续写 prefill 和单 token decode 的并行结构不同；等长与不等长 batch 都应出现。通过计数器区分 Tensor Core 活跃度、指数/向量工作、内存流量和流水线等待，编译与 graph capture 则单独计时。

随后使用真实 head dimension 和 cache layout 做完整模型 prefill，再加入长 prefill 与短 decode 混合流量。比较 TTFT 尾延迟、decode TPOT、成功吞吐和容量。数值检查包含极端 logits 与长序列，再检查模型回答质量。如果内核收益被元数据准备吞掉，或并发 decode 变慢，实验应定位到相应职责，而不是报告为服务收益。

## 依据与核对状态

核对日期为 2026-10-14。

- [FlashAttention-4，2026 年 3 月，v1](https://arxiv.org/html/2603.05451v1)：forward 流水线、软件指数、条件重缩放及论文对比。
- [CuTe 接口，固定 revision `1fc0221183e799363001394a12dd9e78e15f5dda`](https://github.com/Dao-AILab/flash-attention/blob/1fc0221183e799363001394a12dd9e78e15f5dda/flash_attn/cute/interface.py)：架构、dtype、形状和调度分派。
- [同一 revision 的 SM100 forward 实现](https://github.com/Dao-AILab/flash-attention/blob/1fc0221183e799363001394a12dd9e78e15f5dda/flash_attn/cute/flash_fwd_sm100.py)：异步执行与输出修正阶段。
