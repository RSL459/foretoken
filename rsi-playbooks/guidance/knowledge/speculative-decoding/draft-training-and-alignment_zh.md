<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 让 draft 训练对齐实际提交的解码过程

[English](draft-training-and-alignment.md) | 简体中文 | [推测解码](README_zh.md)

## 为什么要区分 draft 来源

小语言模型、EAGLE-3 模块和原生多 token 预测（MTP）头不是可以互换的候选来源。它们的训练输入、对目标权重的依赖、draft 历史和加载条件不同。选择算法的参数无法生成所需的训练权重。值得研究的是训练与服务的分布偏差，以及有效训练成本，而不是把已集成的 EAGLE/MTP 开关当成新方法。

独立 draft 是第二个 token 级语言模型，自己处理前缀。EAGLE-3 同样增加独立训练的辅助模块，但依赖目标内部特征，并可在引擎的模型专属路径中复用目标 embedding 和输出投影。原生 MTP 来自目标架构训练好的辅助预测层，通常无需用户另外提供模型；部分支持的 assistant 路径仍要加载独立检查点。因此“一个模型”指一个目标及其原生辅助计算，不意味着免费预测，也不意味着任意权重都能使用。

## 训练条件与单轮推理

EAGLE-3 融合目标低、中、高层表示，不再像早期 EAGLE 那样要求输出回归目标末层特征。draft 结合融合特征和 token embedding 预测候选。进入尚未验证的位置后，还没有对应目标特征，便用自己此前的 hidden output 继续推测。训练时模拟这条反馈路径，让模块接触多步推测中实际会产生的输入。只看教师强制条件下的准确率无法评价这种行为。

每轮从已提交前缀及目标特征开始。辅助模块延伸一条链，或用同一个模块展开候选树。目标模型一次并行验证候选的因果路径；精确验证只提交被接受的路径和校正或 bonus 输出。拒绝的后缀被废弃，下一轮依据验证后的特征和已提交 token 重建 draft 历史。原生 MTP 遵循相同外层流程，但候选来自架构专属预测层。反复调用一个训练头，不等于拥有多个分别训练的未来位置头。

训练资料需要保留目标身份、tokenizer、chat template、抽取层、位置约定及 loss mask。使用目标自己生成的响应，能够呈现其实际延续行为；离线记录特征可以省去重复目标前向，但也固定了特征与数据分布。在线捕获改变特征的生产位置，并不消除训练需求。更新目标权重、量化方法或 backend，即使张量维度仍兼容，也可能改变特征与概率对齐。

## 成本与当前实现

条件接受率 a[j] 对应的期望候选接受长度是 sum_j product_i<=j a[i]。用未实测的四位置算例说明：[0.9, 0.9, 0.5, 0.5] 产生 2.3175 枚期望接受候选；[0.8, 0.8, 0.8, 0.8] 则为 2.3616。首位置准确率更高，不代表多步 rollout 更好；后者若要更慢的辅助层或特征传递，也不一定划算。

完整成本包括训练与捕获、辅助权重驻留、特征搬运、draft 前向、目标验证和校正。面向持续服务，应把训练投入与累积延迟或容量收益放在一起，而不能只报推理节省、忽略权重生产。原生 MTP 可以省去部分独立抽取或加载，但仍有辅助计算，也继承模型预训练时的选择。

SpecForge 提交 `fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa` 已提供统一的 `specforge train --config ...` 入口及 EAGLE3 在线、离线配方。离线路径读取已记录特征；在线目标推理由 SGLang 捕获服务负责，不是在 trainer 内隐式执行。该快照已删除早期按算法分开的 trainer 命令。vLLM 和 SGLang 已有 EAGLE3 与支持架构的原生 MTP 推理路径，适合作为起点，不应重新宣称为新贡献。

## 有区分力的实验

先用公开、明确匹配的 target/draft 配对；新目标没有辅助权重时，归类为训练项目。对相同留出前缀比较教师强制和自反馈 rollout，记录实际到达数、首次失败位置、接受链长和特征捕获量。按语言、代码、对话、推理分组，避免总体准确率掩盖对齐失败。

修改训练目标时固定目标、数据、训练预算、架构和服务配置，用明确的 optimizer step 比较检查点。逐位置 top-1 一致率、前缀存活率，以及温度/top-p 处理后的真实随机采样接受率要分开。先检查 BOS 重复和模板格式，再把接受率低归因于训练不足；vLLM 的 benchmark preamble 修复已经体现了这个真实混淆因素。

随后在无推测与现有 draft 之间比较未开启 profiling 的服务 TTFT、输出间隔、完成时间、吞吐、显存余量和质量，再单独 profile 特征捕获、辅助 LM head 与通信。值得继续研究的问题是训练应偏重哪些 rollout 深度与任务、引擎变化后离线特征是否仍代表服务，以及更高接受率能否抵消更大的模块。
## 依据与状态

核对日期为 2026-10-14。

- [EAGLE-3 原论文](https://arxiv.org/html/2503.01840)：多层融合、去除特征回归和训练时自反馈机制。
- [固定提交的 SpecForge 训练指南](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/docs/sections/basic_usage/training.md)及[README](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/README.md)说明已实现配方与指标，不代表其中能训练任意 MTP 架构。
- [vLLM EAGLE](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/eagle.md)、[MTP 指南](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/mtp.md)及[SGLang 文档源码](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx)界定当前推理入口。
- [vLLM PR #25916](https://github.com/vllm-project/vllm/pull/25916) 于 2025-10-02 合并，提交 `1cab2f9cad22807150c93b4b5635ff884884ca5a`；preamble 修复是既有 benchmark 行为，不是新的解码优化。
