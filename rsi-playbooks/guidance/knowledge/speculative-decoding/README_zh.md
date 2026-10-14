<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 推测解码

[English](README.md) | 简体中文 | [推理知识](../README_zh.md)

根据生成、验证、校正和提交流程中实际观察到的成本或失败选择机制。

- 固定推测长度有利于单请求，却降低负载下的容量：[用自适应验证预算平衡推测收益与计算占用](balance-speculative-work-through-adaptive-verification-budgets_zh.md)，比较已有动态分段与自适应验证，并核对 runner、graph 和并行条件。
- 训练准确率不错，但多步接受跨度很短：[用自反馈训练改善多步草稿预测](improve-draft-rollouts-through-self-conditioned-training_zh.md)，区分公开 EAGLE3 配对、原生 MTP 和需要新训练权重的目标。
- 增加分支的成本高于挽救路径的收益：[按草稿路径置信度分配候选树验证节点](allocate-verification-nodes-by-draft-path-confidence_zh.md)，计入 SGLang 树与链的 overlap scheduler 差异。
- 多次串行 draft 前向占据整轮主要时间：[用并行块预测消除串行草稿前向](remove-serial-draft-forwards-with-parallel-blocks_zh.md)，从公开 PARD/DFlash 配对与已合并的 DFlash2 集成开始。
- 输出重复，但没有训练型辅助模型：[复用后缀续写生成候选，省去神经草稿计算](avoid-neural-drafting-by-reusing-suffix-continuations_zh.md)，使用已有 Arctic Inference 集成，测量查询成本和历史范围。
- 目标前向结束后，词表处理与校正仍昂贵：[融合拒绝采样，降低保持目标分布的校正成本](reduce-correction-cost-with-fused-rejection-sampling_zh.md)，比较精确逐 token 采样器和受支持的块验证。
- 并行 token 单独合理，组合后却不连贯：[联合选择块内候选，改善草稿续写连贯性](improve-draft-coherence-through-joint-candidate-selection_zh.md)。LiLiCorr 已有实现支持，但引用的引擎文档明确尚无公开 draft 权重，因此仍是训练研究起点。

状态存储与循环层回退见[用重放缓冲区减少循环状态写回](../attention-state/reduce-recurrent-state-writes-with-replay-buffers_zh.md)。这些条目关注废弃未提交候选、从校正历史继续；截短 attention cache 不能恢复所有模型架构。

保留 target/draft 版本、真实 proposal 分布、采样规则、生成/验证/提交长度和调度模式。分阶段时间需要与客户端 TTFT、输出间隔、完成时间、吞吐及 SLO 容量配对。
