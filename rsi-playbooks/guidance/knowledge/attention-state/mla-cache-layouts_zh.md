<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# MLA 缓存布局与 decode 调度

[English](mla-cache-layouts.md) | 简体中文

## 问题与当前上游

Multi-head Latent Attention（MLA）把历史 token 压缩为多个 query head 共享的 latent 向量，减少缓存容量。不过 decode 仍要读取历史、计算各 head 的分数，并合并分片输出。缓存小不等于执行快：scale 读取、离散 gather、反量化和输出投影可能成为主要成本。

FlashMLA 已实现稠密与稀疏 MLA。2026-09-30 的版本变化是重要边界：当前 README 移除了 Hopper 和 DeepSeek V3/V3.2/V4.0 支持，V4.1 还采用不同缓存格式；旧模型明确指向早期固定 commit。因此，“升级到最新 FlashMLA”不是模型无关的优化，已经发布的稀疏内核也不能再作为新方案本身。

## 实际存储与计算过程

简化的 MLA token 包含压缩 latent `c_t` 和位置 key `r_t`。将投影吸收到 query 之后，一个 query head 的计算可写成：

```text
score(t) = q_latent · c_t + q_position · r_t
z        = sum_t softmax(score(t)) * c_t
output   = project(z)
```

缓存里不是每个 head 各自展开后的 K/V。投影吸收减少了存储，同时改变了注意力内核处理的维度与计算量；模型规定的投影和位置语义仍必须保留。

在 breaking change 之前的固定版本中，V3.2 稀疏 FP8 格式每 token 占 656 字节：512 字节 E4M3 latent，16 字节中的四个 FP32 scale，以及 64 个 BF16 RoPE 值占用的 128 字节。每个 scale 对应连续 128 个 latent 值。这是特定模型的物理格式，不是所有 MLA 的通用约定。

当前 V4.1 格式则是 512 个 FP8 值加十六个 E8M0 scale，共 528 字节。FP4 extra-cache 把 512 个 E2M1 值打包为 256 字节，再加 32 个 E4M3 scale。把旧布局交给新内核，不只是快慢不同，而是数值会被解释错。早期 V4.0 的维度以及 page 中 scale 的位置也另有规则。

分页稀疏 decode 接收选中的物理 token 位置。即使 top-k 很小，位置分散到许多 page 后仍会产生不连续读取。split attention 并行计算不同片段，各片段有自己的归一化统计；合并时必须使用 log-sum-exp，而不能直接平均输出。调度元数据决定这些工作怎样分配，必须与当前 decode 配置对应。

## 适用条件与取舍

早期稀疏路径覆盖 SM90/SM100 上的 V3.2/V4.0 MQA 布局。当前仓库描述的是 SM100/SM103 和 Ascend 950 上的 V4.1，软件要求不同，decode 只接受量化缓存。源码列出某平台，不等于整套引擎、模型与 graph capture 在该平台均已验证。

FP8 可能降低带宽并增加请求容量，但 scale、解包和保留的高精度部分会削弱理想字节收益。FP4 又改变精度和内核适用范围。稀疏选择改变“读取哪些 token”，缓存量化改变“读取到什么值”，两者应分别比较。小 batch 可能受 launch 限制，长上下文高并发才可能进入带宽受限区间。

## 实现入口与剩余设计空间

先依据目标模型选择 FlashMLA README 与 API，再查看 `get_mla_metadata`、`flash_mla_with_kvcache`、indices 和引擎缓存写入方。序列长度、top-k、query 数或 head 配置改变之后，应重新核对元数据是否仍有效，不能把“可以复用”理解成永久不变。

剩余问题包括布局感知 gather 顺序、scale 复用、不等长序列的 split 选择，以及缓存写入或反量化融合。调整读取顺序必须保留 indices、数值和位置特征的对应关系。异构设备可能需要不同 tile 调度，但不应改变模型缓存语义。如果主要成本来自选择 token，应转向[稀疏索引器路由](sparse-indexer-routing_zh.md)，而不是只调 MLA 消费方。

## 从局部到服务的实验

性能比较前，先构造 latent、scale 与位置值均可独立识别的缓存行。scale 放错位置或布局转置可能仍产生看似合理的输出。先固定 indices，比较量化与高精度缓存，再单独比较稀疏与稠密，避免归因混淆。

扫描上下文长度、batch、选中 token 数、page 局部性和 query 数，包含 speculative 多 token query。记录真实读取字节、有效带宽、scale/反量化、分片归约和元数据准备成本，再进入包含缓存写入与输出投影的完整模型执行。服务比较分别使用相同内存预算与相同并发，报告 TPOT 尾延迟和成功吞吐，避免把容量提升当成单请求加速。长上下文质量检查应包含检索和位置敏感任务。

## 依据与核对状态

核对日期为 2026-10-14。

- [FlashMLA 当前 README，固定 `2e5429fc5653bab6e081f09477126f731882a6a9`](https://github.com/deepseek-ai/FlashMLA/blob/2e5429fc5653bab6e081f09477126f731882a6a9/README.md)：V4.1 格式、硬件范围、API 与 9 月 30 日 breaking change。
- [明确指定的旧 revision `ba89a3466e9470ad08ab39738d4e7bb66989e1e7`](https://github.com/deepseek-ai/FlashMLA/blob/ba89a3466e9470ad08ab39738d4e7bb66989e1e7/README.md)：V3.2/V4.0 布局与早期稠密/稀疏 decode 约定。
- [DeepSeek-V3.2 报告 v1](https://arxiv.org/html/2512.02556v1)：DSA 使用 MLA MQA 的方式及模型级稀疏选择。
