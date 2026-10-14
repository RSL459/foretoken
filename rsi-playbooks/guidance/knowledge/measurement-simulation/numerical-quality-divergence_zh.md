<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 数值差异、贪心分歧与答案质量

[English](numerical-quality-divergence.md) | 简体中文 · [测量与模拟](README_zh.md) · [推理知识](../README_zh.md)

## 三个问题需要三种比较

内核变化可以改变 logits，却不改变概率最高的 token；很小的 logit 变化，也可能交换两个近似并列的 token，使后续自回归生成进入不同上下文。这两种观察都不能单独确定任务准确率。数值保真、生成序列一致与答案质量有关，但不是同一问题。

浮点加法不满足结合律。不同 batch 或切片可能选择不同归约和内核，低精度又会改变舍入。PyTorch 数值精度文档没有承诺这些执行安排间的逐 bit 一致。固定 seed 控制随机选择，不会固定归约顺序，也不会使 greedy argmax 对数值扰动免疫。

## 微小扰动为什么能改变贪心输出

参考 top 两个 logit 为 z₁、z₂，间隔 `m=z₁−z₂>0`。若候选每个 logit 的误差不超过 ε，则 `m>2ε` 足以保证最大项不变。间隔更小时，微小扰动也能反转排序。这个充分条件要求相同词表与前缀；整体 RMSE 不是逐元素误差上界。

例如 10.000 与 9.999 相差 0.001，分别扰动 −0.0006 与 +0.0006 就会换序。此时 softmax 分布仍可能极接近。一旦不同 token 进入下一步前缀，后续差异包含上下文变化，不能全部归因于最初的内核误差。

## 固定前缀分布隔离局部影响

Teacher forcing 在每个对照位置提供相同 token ID，避免上下文漂移。参考分布 p 与候选 q 的 `KL(p||q)=Σpᵢ log(pᵢ/qᵢ)` 按参考概率质量加权；总变差为 `½Σ|pᵢ−qᵢ|`。Top-1 一致率反映 argmax 稳定性，top-k 重合率反映合理候选集合变化，各指标揭示不同侧面。

完整词表 KL 需要完整分布。Top-k 截断会遗漏质量，不同 token ID 解码出的文本还可能相同。Foretoken 对照客户端要求 token-ID key，并在归一化序列化误差前核对词表覆盖和概率质量。两端应使用相同 ID 映射、模板、特殊 token 处理及词表，否则比较的不是同一个预测问题。

共同 logit 偏移不改变 softmax，centered-logit RMSE 因此去掉公共偏移；但它仍可能被许多极低概率 token 的变化主导。应一起看高 KL 位置、argmax 间隔、语料 token 概率和任务类型。短通用文本窗口不能代表长上下文检索边界或结构化工具输出。

## 自由生成暴露另一类问题

贪心序列对照能观察实际反馈下的首次分歧、EOS 和完全一致率，适合预期保留 token 选择的实现变化。但序列不同不自动等于质量下降，两种续写可能都正确；简单样本上的高一致率也会遗漏少见的重要错误。

vLLM 已有 batch invariance，核对文档将其标为 beta，并限制硬件、模型和张量并行。它会改变内核选择且可能有性能成本，适合在支持范围内作为诊断对照。开放 issue #51187 的复现报告并发重复运行时 logprob 不同，但输出 token ID 相同，原因仍未确定。

## 区分错误与不稳定性的实验

先让未修改参考实现重复执行串行和代表性并发，观察其自身波动。再用相同固定前缀，跨上下文、batch、精度与图模式比较候选。若只随批次形状变化，检查归约和分派；若大误差集中在某层或状态切换，调查 correctness 缺陷，而非笼统归为浮点波动。

对于较早的 greedy 分歧，在相同分歧前前缀上比较两端分布和间隔。明显分布漂移与近似并列翻转是不同问题。使用原生 token ID 和 finish reason，不要重新分词可见文本来代替。最后以相同评分规则做配对任务评估，检查改变的答案，包含与优化相关的长上下文及结构化输出。质量、性能与精确复现分别形成结论，不能互相代替。

## 来源与实现状态

核对日期：2026-10-14。

- [PyTorch 2.9.0 数值精度](https://github.com/pytorch/pytorch/blob/v2.9.0/docs/source/notes/numerical_accuracy.rst)：batch、归约顺序、后端精度及非逐 bit 保证。
- [vLLM batch invariance](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/batch_invariance.md)：2026-10-13 revision 的 beta 范围和取舍。[Issue #51187](https://github.com/vllm-project/vllm/issues/51187)创建于 2026-08-05，核对时仍 open，报告明确区分 logprob 波动与 token 分歧。
- [Foretoken 分布对照](../../../../benchmarks/docs/eval/distribution-comparison_zh.md)及[客户端](../../../../benchmarks/src/benchmarks/integrations/distributions.py)：以 `e6ae3df6` 核对 teacher forcing、原生 greedy ID、完整概率向量和指标公式。
