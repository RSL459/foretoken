<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 用并行块减少串行 draft 前向

[English](parallel-diffusion-drafting.md) | 简体中文 | [推测解码](README_zh.md)

## 串行成本来自哪里

目标模型很快，不代表整轮推测很快。自回归 draft 提议 K 枚 token，可能需要 K 次串行辅助前向，每次都支付 launch、attention 和输出投影成本。并行 drafting 用一次块预测替代这条计算链，但不会把目标模型改成非因果模型，也不保证各位置单独合理的候选能组成连贯续写。

PARD 与 DFlash 通过不同方式消除依赖。PARD 改造普通小自回归模型，用 mask 占位符并行预测多个未来位置；它不读取目标 hidden representation，可在兼容的目标之间复用。DFlash 则是独立训练、依赖目标所选特征的轻量块扩散 draft。两者都使用一个目标加一个辅助模型，都不是无需训练的 prompt 复用。

原始 DFlash 的流程很具体：一个已验证 anchor 开始候选块，其余位置 masked，通过一次 draft 前向同时预测。draft 块内允许双向交互，但目标验证仍是因果自回归。这里的“扩散”不应被理解为必须进行长串去噪迭代，论文评价的是单步块预测。

## 单轮过程与训练条件

目标 prefill 或上轮提交后，将 anchor 和已提交上下文交给 draft。DFlash 拼接目标所选层特征，投影、归一化，再作为额外 key/value 输入 draft 层，随后并行生成未验证位置。PARD 则从 token 上下文构造带 mask 的预测输入，不需要这条目标特征接口。

目标在因果 mask 下对候选线性续写执行一次前向。贪心模式接受与目标选择一致的前缀，首次不匹配时输出目标校正。随机提议的精确验证需要真实 proposal 分布，不能把任意逐位置原始 logits 当成最终联合采样器。提交验证前缀和校正/bonus，废弃其余部分。用已提交的目标特征或 token 延伸 draft 上下文，而不是保留整个未验证块。

DFlash 训练冻结目标，使用目标生成的响应，选择干净 anchor 并 mask 未来位置。块内双向 attention 和训练块分离与提议布局一致；早位置 loss 权重更高，反映首错会使后续候选失效。PARD 使用未来位置 mask 目标及条件丢 token 训练降低适配成本。公开权重是最短实验路径，换目标不会自动使一个 DFlash 检查点兼容。

## 成本与部署边界

在期望提交长度 L 相近时，串行路径近似花费 K*draft_forward + verify(K) + correction；并行路径花费 block_forward(K) + feature_handling + verify(K) + correction。块前向本身也随宽度增大。即使大多数位置被拒绝，K 增长仍会增加目标行数、LM head 工作与缓冲。

用未实测算例说明：六次 draft 前向变成一次，只有块前向、特征处理与验证增量之和低于原六次成本时才有效。一个 16 位置块若很早不一致，可能只提交一枚校正。此时截短验证只能省目标工作，无法退回已经完成的 draft 前向；详见[自适应验证](adaptive-verification-budget_zh.md)。

vLLM 当前文档已有 `amd/PARD-Qwen3-0.6B` 配合 `parallel_drafting: true` 的示例。DFlash 官方项目列出公开、目标专属的权重。DFlash2 的局部卷积与候选选择器也已通过 vLLM #52816、SGLang #35371 合并。使用这些集成时，需要匹配的检查点。

SGLang 提交 `e9400c5a8f3a0d0312a37aecef694f5edfd69341` 中，DFlash 验证线性块，可从配置推断块大小；draft window 至少覆盖块。文档路径不支持流水线并行或 DP attention，并关闭 overlap scheduler 与 mixed chunked prefill。比较时应以这些实际执行模式为准，不能假定所有通用推测配置都能组合。不同引擎的块大小可能包含 anchor；vLLM LiLiCorr 文档明确以训练块大小减一计算推测位置。

## 实验与研究空间

先用公开、匹配的 target/draft 权重在指定引擎版本上建立实际可运行路径。固定采样、输出和并发，比较无推测、自回归 EAGLE3 和并行块。扫描块宽与上下文长度，分别 profile draft 层、特征搬运、词表投影、目标验证、校正及 graph/主机空隙，再进行不带 profiler 的服务 TTFT、输出间隔、完成时间、吞吐、显存余量和 SLO 容量比较。

为了区分减少串行成本与提高预测质量，尽可能比较相同期望提交长度，并报告生成、验证和提交位置。覆盖 prefill/启动占主要成本的短输出，以及验证争夺容量的饱和混合流量。不同方法改变 scheduler overlap 的影响应该进入结果，而不是隐藏的实验差异。

未解决问题包括如何保持块内连贯性，缩短上下文窗口时怎样保留领域续写能力，以及变长验证如何保留引擎已有功能。[联合候选选择](joint-block-candidate-selection_zh.md)专门研究连贯性，机制与减少串行前向不同。

## 来源与状态

核对日期为 2026-10-14。

- [PARD v4](https://arxiv.org/html/2504.18583v4)：并行 mask、目标独立性及适配训练；[vLLM 固定提交示例](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/parallel_draft_model.md)。
- [DFlash 原论文](https://arxiv.org/html/2602.06036)：特征条件单步 draft 与训练。[官方仓库](https://github.com/z-lab/dflash)在 `07ebd93db9f472af339b644bb70221ad8428328a` 列出公开模型合集。
- [vLLM #52816](https://github.com/vllm-project/vllm/pull/52816) 于 2026-08-21 合并为 `b389ac29465b33f9e9c534df221ea3c129e9793f`；[SGLang #35371](https://github.com/sgl-project/sglang/pull/35371) 于 2026-08-19 合并为 `c14312a66420b75ca9a11bf1817c4db1fa26b097`。
- [SGLang 固定文档](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx)及[SpecForge 训练指南](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/docs/sections/basic_usage/training.md)说明推理与训练边界。
