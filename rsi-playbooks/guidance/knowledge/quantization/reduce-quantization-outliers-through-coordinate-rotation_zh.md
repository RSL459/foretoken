<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 用坐标旋转分散离群值，降低量化误差

[English](reduce-quantization-outliers-through-coordinate-rotation.md) | 简体中文

一块激活中只要有一个特别大的坐标，量化范围就可能主要服务它。旋转先将能量分散到不同坐标，再执行量化。它是否有价值，既取决于误差变化，也取决于变换能否折叠到权重，还是必须在线执行。

## 改坐标而不改线性映射

按行排列输入，`Y = X Wᵀ`。若 `R Rᵀ = I`，令 `X′ = X R`、`W′ = W R`，则 `X′ W′ᵀ = X Wᵀ`。未量化时计算完全等价，但量化器面对的分布改变了。

将 `[a,0]` 乘以归一化 Hadamard 矩阵，会得到 `[a/√2,a/√2]`，保持范数而降低最大幅度。长向量也可能不再由少数通道主导，不过这不保证每个 scale block 都更合适。全局旋转、块内旋转和排列，与每 16 或 32 个值共享 scale 的边界有不同关系。

执行应依次收集通道与块统计、选择变换、将可离线部分折叠到相邻权重、插入必要在线变换，然后重新校准量化器。沿用旋转前的 scale 会混淆效果。任意旋转一般不能穿过 SiLU 或门控乘法；这类非线性之后可能仍需在线变换，与改变后的 down projection 配对。

引用版本的 SpinQuant 实现修改 embedding、attention 输入输出、MLP 输入输出和语言模型 head，其中 down projection 包含逆 Hadamard 权重变换。这是一组具体模型重写，不代表可以任意旋转 hybrid 模型的所有模块。bias、norm、残差、共享专家和 tied weights 都应处在一致的坐标系中。

## 上游已有能力与近期研究

llm-compressor 已列出 SpinQuant 和 QuIP。SpinQuant 作者仓库提供学习旋转和 ExecuTorch 导出。在 vLLM 部署取决于导出格式及目标 backend 对所需在线变换的支持。

TORQ（arXiv 2605.19561v1）将 MXFP4 激活问题区分为块间能量不均衡和块内码本利用不足。方法构造 `R = R_inter ⊗ R_intra`：用 Givens rotation 均衡块间协方差对角项，块内旋转与 scale 更新交替，降低码本占用不均衡 `Σ_j (p_j−1/J)²`。方法章节和执行图仍保留在线激活旋转，将逆变换折叠到 consumer 权重。论文报告了质量和 RTX 5090 速度结果，但未定位到具体已合并的上游 serving 路径。值得继续测的是两级结构能否以足够的留出集质量改善，抵偿在线变换成本。

对于 NVFP4、MXFP4 和整数 W4A8/W4A16，仍需判断什么变换范围能以可接受在线成本改善质量。小 decode batch 下，在线变换可能比量化 GEMM 节省的时间还长；更密集的变换也可能增加重排后的权重误差，或破坏现有激活量化融合。

## 误差与变换必须一起测

使用同一校准语料和最终格式，比较不旋转、已有固定 Hadamard 方法和已有学习旋转。检查块最大值、方差分布、clipping、码本占用和留出集层输出误差。先确认变换后 BF16 模型等价，再归因到量化。局部计时覆盖在线变换、量化和 GEMM，并采用真实 decode、prefill 形状。

服务侧比较答案质量、TTFT、TPOT 与真实输出长度，同时覆盖校准领域和分布迁移输入。质量恢复即使增加延迟，也可能支持更小的部署，但需要明确说明交换条件。
## 参考

- [SpinQuant 源码，commit 8f47aa3f00e8662caf1a484153920a07e5281c3a](https://github.com/facebookresearch/SpinQuant/blob/8f47aa3f00e8662caf1a484153920a07e5281c3a/eval_utils/rotation_utils.py)，提交于 2025-02-14。
- [当前 llm-compressor 方法](https://github.com/vllm-project/llm-compressor/tree/990fdd2fb41af48f105dbdebd088a96b627701b1)。
- [TORQ 方法、执行图与限制，v1](https://arxiv.org/abs/2605.19561)。

[量化问题索引](README_zh.md) · [Kernel 设计](../kernel-design/README_zh.md) · [知识索引](../README_zh.md)
