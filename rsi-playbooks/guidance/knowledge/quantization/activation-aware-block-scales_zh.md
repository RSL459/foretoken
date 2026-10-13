<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 根据激活选择块 scale

[English](activation-aware-block-scales.md) | 简体中文

两组权重的重建误差相同，对模型的影响却可能不同。只按权重最大值选 scale，没有考虑实际工作负载使用哪些输入方向。近期 NVFP4 校准方法直接优化输出误差，同时保留既有推理表示。

## 优化真正传到输出的误差

将输入按列排列，写成 `Y = W X`。设某 scale 下的反量化权重为 `Q(W,s)`，误差为 `Δ = Q(W,s) − W`。普通权重 MSE 最小化 `||Δ||²`；校准输出误差则为：

```text
E = ||Δ X||²_F = tr(Δ H Δᵀ),   H = X Xᵀ。
```

`H` 是输入二阶矩，在这里常称 local Hessian，不需要估计整个模型损失的完整 Hessian。如果两个通道的输入方差分别为 100 和 1，相同权重误差造成的输出误差不同。通道相关性也会让误差在常见输入方向上叠加或抵消。

Model Optimizer 的 Local-Hessian 将输入轴划为每块 16 个 NVFP4 值，累计对应的 `16×16` 二阶矩，枚举可表示的 FP8 scale，按 `Δ_b H_b Δ_bᵀ` 选择。官方说明描述了 126 个正且非零 FP8 scale 候选。各块独立让计算可行，但忽略不同块之间的误差相互作用。

过程是收集激活、累计统计、选 scale，再导出普通 NVFP4 权重与元数据。按层校准可让后续层消费先前层的 fake-quantized 输出，避免假定全部输入仍是 BF16。部署时不需要新的“Local-Hessian kernel”，只需现有 NVFP4 格式 kernel。

## 浮点码本为什么需要不同 scale

Four Over Six 提供了另一种直观解释。E2M1 间距并不均匀，较大的正值包含 4 和 6。通常将最大值缩放到 6 附近；另一种规则将其放到 4 附近，改变整块的重建精度分配，再用误差选择。这里的“四”不是换成另一种 bit 数，也没有替换原生 E2M1 码本。

例如 `[10,20,30,40]` 最大值缩放到 4，scale 为 10，E2M1 `[1,2,3,4]` 可以精确重建；缩放到 6 则在第三个值附近产生误差。另一块可能更适合 6，所以要重建两个候选再比较。论文明确说明相同 4/6 选择不能直接用于 MXFP4：所需 1.5 倍 scale 变化通常无法由二次幂 E8M0 表示。当前作者仓库默认用 MSE 选择，并提供 Blackwell CUDA/Triton 实现和较慢的 PyTorch 参考。README 中的新 adaptive block-scaled types 是另一条工作，不能与 4/6 混写。已核对的 ModelOpt 已公开 Local-Hessian 校准实现；不应把重新实现它当成引擎优化机会。

## 尚需针对负载决定的部分

这些方法面向导出为 NVFP4 的 dense 或 MoE 线性权重，部署范围由既有 runtime backend 决定。真正待选的是校准分布：领域、语言、上下文长度和稀有专家覆盖。某个专家几乎没有校准 token 时，再完整的 scale 搜索也不能补上缺失的统计。

比较最大值、权重 MSE 与 Local-Hessian 三种 scale，保持 payload 格式和推理 backend 不变。记录权重误差、留出激活的输出误差、专家 token 数和任务质量，并加入未进入校准的代码或长上下文切片。完整服务仍使用相同布局测延迟；质量改善而 GEMM 不变也是有效结果。

质量仍差时，先检查跨块误差和覆盖不足的层，而不是无限增加校准。增加成本应依据留出集行为，而非仅凭训练集重建损失下降。
## 来源

核对日期：2026-10-14；ModelOpt 快照 `b5f10f8bf96201241c35b86498557bd6fdde10ca`。

- [Local-Hessian 方法、接口与限制](https://nvidia.github.io/Model-Optimizer/announcements/local-hessian.html)。
- [校准实现](https://github.com/NVIDIA/Model-Optimizer/blob/b5f10f8bf96201241c35b86498557bd6fdde10ca/modelopt/torch/quantization/model_calib.py)。
- [Four Over Six 论文，arXiv 2512.02010v5](https://arxiv.org/abs/2512.02010)与[作者实现](https://github.com/mit-han-lab/fouroversix)。已核对方法与实现章节，作者仓库快照为 `dadfad6901d473a734fe71e0b082e70ee993e23a`（2026-04-21）。

[量化问题索引](README_zh.md) · [知识索引](../README_zh.md)
