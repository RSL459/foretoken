<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 按验证成本分配推测预算

[English](adaptive-verification-budget.md) | 简体中文 | [推测解码](README_zh.md)

## 问题与机制

固定 draft 长度用更多单轮计算换取更少的目标模型解码轮次。并发、上下文长度和计算余量改变后，这笔交换也会改变。单请求有效的配置，在接受率不变时仍可能降低服务容量。因此优化目标应是单位服务占用时间内提交的输出，而不只是候选接受比例。

这里有两个不同决策：生成多少候选，以及验证多少候选。自回归辅助 draft 可以提前停止，省去后续前向；一次前向完成的并行 draft 已经付出了生成成本，截短通常只节省验证。自适应验证使用一个目标模型及现有辅助 draft，不增加第二个辅助模型。候选仍是链或线性块，改变每个请求获准验证的长度，并不要求改变拒绝采样规则。

设 a[r,j] 是请求 r 在前序候选均被接受的条件下，第 j 个候选的接受概率；s[r,j] 是这些条件概率的累积乘积。批次目标可以近似写为：

```text
期望提交量 / 单轮时间
= sum_r (1 + sum_j<=K[r] s[r,j])
  / (draft 时间 + verify 时间(总获准位置数、上下文) + 校正和提交时间)
```

额外的 1 是普通链式推测的一枚校正或 bonus 输出，不是另一枚被接受的 draft；EOS 和输出上限会截断这项计数。分配长度必须是连续前缀，不能只按单位置置信度选择而忽略父位置。

考虑一个未实测的算例：A、B 的前缀存活率分别为 [0.9, 0.8, 0.7] 和 [0.5, 0.2, 0.05]。四个验证位置可以给 A 三个、B 一个，期望接受 2.9 枚候选；平均分配则为 2.4 枚。只有布局整理、graph 填充、估计器和状态记账没有抵消收益时，这个分配才值得采用。

## 单轮流程与已实现边界

先用现有 draft 生成候选块，估计各位置的前缀存活率，再根据测得的步长成本选择总预算，并给每个请求保留连续前缀。目标模型按正确的因果历史评估这些位置。验证接受前缀并采样校正 token；整段成功时追加目标 bonus。随后只提交这些输出，丢弃所有未提交候选，包括已经生成但根本没有验证的位置。下一轮 draft 必须从提交历史出发，而不是从最长的生成块出发。

vLLM 提交 `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9` 的文档已经覆盖 EAGLE、MTP、DFlash、DSpark 和独立 draft 模型的自适应验证。DSpark 可以使用训练过的置信头；其他 draft 使用以验证结果在线校准的逻辑回归估计器。启动阶段测量单轮成本曲线。这些属于当前实现，不是尚待集成的研究提案。

该快照要求完整 CUDA Graph，以及能容纳设备侧决定 query 长度的 attention backend；不支持 LoRA 和流水线并行。启动成本测量默认使用 8192 token 的合成上下文，远长于此的服务负载可能使估计失真。另一条已有路径 `num_speculative_tokens_per_batch_size` 按批大小降低 K，甚至设为零；其文档不支持数据并行，因为不同 rank 独立选择 K 可能造成 collective 顺序分歧。批大小分段策略与设备侧逐请求预算不是同一机制。

## 能区分策略的实验

先比较无推测、固定长度和已有批大小策略，再比较固定生成长度下的完整验证与自适应验证。保持目标/draft 权重版本、采样、输出长度分布、graph 模式和调度器一致。除了同质请求，还要把容易重复的输出和困难推理混入同一批次；后者的分配空间会被总体接受率掩盖。

将负载推到饱和，并覆盖短、长上下文。分别记录生成、获准验证、实际到达、接受与最终提交的位置数，分位置校准误差，实际布局与 captured graph 大小，draft、verify、sampling 时间，以及浪费的目标行。服务侧观察 p50/p99 TTFT、输出间隔、请求完成时间、输出吞吐、错误和满足 SLO 的持续请求率。直接执行中途改变 K、取消、EOS 和零候选轮次，检查长度元数据与提交边界能否闭环。

研究空间不是“是否可以动态调整”，而是当前负载的上下文成本与接受估计是否值得比简单负载分段更细的预算。领域漂移下的校准、过期的启动曲线和 graph 向上取整都有明确测量对象。状态恢复另见[递归状态推测回放](../attention-state/recurrent-speculation-replay_zh.md)。

## 依据与状态

核对日期为 2026-10-14。

- [固定提交的自适应验证文档](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/adaptive_verification.md)和[批大小策略文档](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/dynamic_speculative_decoding.md)界定该快照的支持范围。
- [PR #47808](https://github.com/vllm-project/vllm/pull/47808) 的置信调度验证于 2026-08-12 合并，提交为 `7f7a32cfec0f1bc5b73c37200b86631523a1ea8f`。
- [RFC #48202](https://github.com/vllm-project/vllm/issues/48202) 讨论包含低负载未获益及饱和场景的贡献者报告，不是 Foretoken 证据。其中[PR #48692](https://github.com/vllm-project/vllm/pull/48692) 已关闭且未合并，不能由此推断当前主线没有相应机制。
