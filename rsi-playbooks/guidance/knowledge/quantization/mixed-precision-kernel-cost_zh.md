<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 考虑实际 kernel 成本的混合精度

[English](mixed-precision-kernel-cost.md) | 简体中文

不同层的量化敏感度不同，统一低位会给它们分配相同精度预算。混合精度可以在内存预算内保留质量，但平均 bit 数并不能预测延迟。可执行的分配还要符合引擎融合边界和设备实际 kernel。

## 按敏感度分配精度

Model Optimizer AutoQuantize 对每个可量化算子 `i` 和格式 `f`，用对角 Fisher 近似估计输出误差敏感度：

```text
S_i,f ∝ Σ_k g_i,k² (Y_i,k − Y^Q_i,f,k)²。
```

其中 `Y_i` 与 `Y^Q_i,f` 分别为参考和 fake-quantized 算子输出，`g_i,k = ∂L/∂Y_i,k` 是评分损失的输出梯度，k 遍历输出元素；分数汇总校准观察。它捕获输入、取得输出梯度，局部重放候选量化器，再通过整数规划，在有效 bit 预算下给每个算子或部署组选择一种格式：

```text
min Σ_i S_i,f(i)，约束 Σ_i N_i b_i,f(i) ≤ N_total b_target。
```

`N_i` 是算子 i 参与搜索的权重数，`b_i,f` 是格式 f 的每权重 bit 成本，`N_total = Σ_i N_i`，`b_target` 是目标平均 bit 数。只有参与搜索的可量化权重计入该预算；被排除的 embedding 和 norm 仍占内存。有效 bit 可以反映部分格式元数据，但这不是服务延迟目标。

当前实现会将 QKV、gate/up projections、稀疏专家等部署决策分组，因为 runtime 可能合并权重或要求同一量化契约。独立给 Q、K、V 三种格式，可能得到数值上好看、却不能使用现有融合投影的方案。组内敏感度与成本相加，也没有表示所有误差交互。

例如两个等大小层组，一个在四位下明显更敏感，则四／八位分配可能比统一六位预算更好。但四位组的大 M 执行可能走 W4A16，八位组却有更快原生 FP8 kernel。bit 预算最优不等于延迟最优。

## 复用已有搜索，测量缺失的成本

已核对的 Model Optimizer 开发快照已经公开 AutoQuantize、梯度和 KL scoring。该方法采用局部敏感度、对角曲率、分组约束及有效 bit 代理成本。

剩余收益空间是按负载选择可部署方案。测每个候选组在真实 decode/prefill 形状下的完整阶段成本，包含量化、补齐、输出处理与格式转换。格式组合是否可导出和执行，应沿用既有 exporter/runtime 边界，不建立另一套检查点协议。FP8、NVFP4、MXFP4、BF16 的选择依赖硬件原生指令、MoE 布局和模型排除项。

精度变化还可能改变 scratch 内存、graph capture 占用和最大 batch，因此完整服务中的组成本不能简单相加。延迟感知扩展应先看实测组合与瓶颈，不能把“以一个微基准替换 bit 数”描述为已解决全局分配。

## 区分预算收益与速度收益

在类似内存预算下比较统一低位、现有 AutoQuantize，以及对一个敏感或慢组的实测调整。保持校准语料和质量评测一致，记录常驻权重、scale/padding、转换时间、实际 kernel 和留出集质量。组重建误差用来诊断，不代替最终质量。

完整服务覆盖低并发和目标负载，观察 TTFT、TPOT、成功 token 吞吐、输出长度与可接纳并发。节约内存可能通过更大 batch 改善吞吐，却损失低负载延迟。调整某组同时提升质量与速度时，应保留对应模型、形状、dtype 和设备条件，不泛化为所有层的规律。
## 来源

核对日期：2026-10-14。

- [AutoQuantize scoring、搜索、分组与限制](https://nvidia.github.io/Model-Optimizer/announcements/autoquantize.html)，ModelOpt 快照 `b5f10f8bf96201241c35b86498557bd6fdde10ca`。
- [vLLM 可执行 ModelOpt 格式](https://docs.vllm.ai/en/latest/features/quantization/modelopt/)。
- [SGLang 当前量化 backend](https://docs.sglang.io/advanced_features/quantization.html)。

[量化问题索引](README_zh.md) · [异构执行](../heterogeneous-hardware/README_zh.md) · [知识索引](../README_zh.md)
