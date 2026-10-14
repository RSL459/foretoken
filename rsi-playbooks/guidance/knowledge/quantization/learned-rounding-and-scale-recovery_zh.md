<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 学习舍入与 scale 恢复

[English](learned-rounding-and-scale-recovery.md) | 简体中文

就近舍入最小化单个数值的即时误差，并不直接最小化 transformer block 的输出误差。直接校准损失较多质量时，可以增加离线优化，同时保留现有低位部署格式。应区分优化的是舍入决策、scale，还是模型权重本身。

## 从逐值误差转向 block 输出

设 BF16 block 为 `F_l`，fake-quantized block 为 `F̂_l`，校准隐状态为 `h`：

```text
L_block = Σ_h ||F̂_l(h; θ) − F_l(h)||²。
```

整数格式可以学习相邻可表示值之间的舍入选择。浮点相邻值间距不均匀，scale 与 clipping 又决定数值落在哪个区间，因此优化必须使用真实 fake quantizer，不能把均匀整数量化近似当成 FP4。

已核对的 llm-compressor AutoRound NVFP4 示例描述了顺序处理 decoder layers，学习 `V`、`α`、`β` 来优化舍入与裁剪。流程是捕获 block 输入和 BF16 输出、针对重建误差优化、冻结选择、导出 compressed-tensors，再由 vLLM 加载。该流程上游已经存在；收益是同一最终格式下改善重建，不是在线增加优化器。公开 Llama-3.1 示例也说明更多迭代不保证更好：200 次迭代相对零次改善一种 GSM8K 提取评分，却降低另一种。应检查目标答案与评分行为，不只看重建损失。

Model Optimizer 的 scale learning 则训练 NVFP4 每块权重 scale，用 `amax` 参数、fake quantization 与直通梯度估计。当前支持只学 scale，或同时学权重与 scale。先用 MSE 校准初始化，示例监测类似蒸馏的 KL 目标。最终 scale 仍需投影到 NVFP4 的 FP8 表示，连续参数上的低损失不保证导出后仍一样好。

每 16 个权重只学一个 scale，可减少训练参数与 optimizer state；这不等于每次前后向计算也减少十六倍。官方说明中较短训练和学习率是对应模型的起点，而不是通用要求。当前范围是 NVFP4 每块权重 scale，全局和激活 scale 学习仍被文档列为后续扩展。

## 什么时候值得额外恢复

当 W4A4 NVFP4 或其他已支持格式接近可接受质量时，这些方法值得比较。它们不能补偿 kernel 不支持、导出损坏或架构不匹配。顺序 block 重建可能遗漏跨层作用；只学 scale 无法任意移动权重；联合训练需要更多算力、数据和状态。

剩余设计空间是选最小但有效的恢复过程：校准样本、专家覆盖、block 划分、初始化，以及 scale-only 是否足够。MoE 校准需要真实路由 token。不能因为整体 block loss 下降，就宣布几乎未被访问的专家也恢复了。

## 将恢复效果与部署性能分开

相同模型和校准／留出集下，对比直接校准、已有 AutoRound、scale-only 恢复。记录离线时长、峰值内存、重建误差、任务得分和专家覆盖；联合训练另报不同的训练状态预算。导出后在目标引擎重新加载，确认实际 kernel 和 scale 粒度符合设计。

局部计时包含激活量化与一个代表性 MLP/MoE 的全部投影，门控 MLP 包含 gate/up 和 down projections。完整服务观察质量、TTFT、TPOT、成功 token 吞吐和输出长度。理想情况是改善质量而不新增 runtime 算子；如果导出后悄然选择了另一 backend，就应另行归因。
## 来源

核对日期：2026-10-14；源码快照见[分类入口](README_zh.md)。

- [llm-compressor AutoRound NVFP4 示例](https://github.com/vllm-project/llm-compressor/tree/990fdd2fb41af48f105dbdebd088a96b627701b1/examples/autoround/quantization_w4a4_fp4)。
- [Model Optimizer scale learning 方法与范围](https://nvidia.github.io/Model-Optimizer/announcements/scale-learning.html)。
- [vLLM 部署格式](https://docs.vllm.ai/en/latest/features/quantization/modelopt/)。

[量化问题索引](README_zh.md) · [MoE 执行](../moe-execution/README_zh.md) · [知识索引](../README_zh.md)
