<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 让并行 draft 候选组成连贯路径

[English](joint-block-candidate-selection.md) | 简体中文 | [推测解码](README_zh.md)

## 与并行生成不同的问题

并行块预测省去了串行辅助前向，但逐位置合理不代表组合合理。draft 可能在开头生成一个标识符，后面却引用另一个；每个 token 单独看都常见，组合却不一致。目标验证拒绝不连贯前缀，于是边际准确率很高，实际提交跨度仍短。联合候选选择研究能否在支付目标验证前，用少量额外 draft 计算改善一致性。

LiLiCorr 建立在 DFlash 辅助模型上，不再引入另一个完整语言模型。系统包含一个目标、一个 DFlash backbone 和训练过的关联头。DFlash2 也已提供训练型候选选择器及局部卷积，因此“给候选增加相互依赖”并不是引擎中不存在的方向。不同机制和权重条件必须分清，不能把任意 selector 都叫 LiLiCorr。

当前这是训练/研究候选，不是直接部署配方：检查到的 SGLang 文档明确说明尚未发布 LiLiCorr draft。已有加载实现不等于已有训练好的关联权重。只有普通 DFlash 权重时应使用既有路径，不能靠改 architecture 名称制造兼容头。

## 机制与单轮过程

给定已提交前缀和已验证 anchor，DFlash 为块内每个未验证位置生成 top-k 候选。LiLiCorr 用小型双向 transformer 联合编码整个候选格，为候选生成 incoming/outgoing 向量，以它们的相似度计算相邻位置配对兼容性。配对得分可以批量求出，不需要为每个最终选择 token 串行执行神经前向。随后从左向右，在前面选择的条件下选出一条路径。

原论文联合训练 DFlash 与关联头，使用 oracle 前缀交叉熵和目标加权的干扰候选惩罚。候选覆盖是必要条件：目标 token 不在 top-k 中，selector 无法把它找回来。因此已有 plain DFlash 加上未训练关联头，不满足方法前提。

路径选出或抽样后，用普通因果目标验证。如果选择是确定性的，每步 q 为选中 token 的点质量；如果沿路径随机采样，需要提供真正走到的位置所用归一化条件分布，而不是 backbone 的逐位置概率。精确验证接受并校正，只提交接受链及校正/bonus，丢弃其他格路径和拒绝后缀。正确性仍属于目标验证器，关联头只争取降低单位提交 token 的提议成本。

## 成本与诊断算例

m 个位置、每个 k 个候选，相邻配对约有 (m-1)*k*k 条边。m=15、k=8 时是 896 个配对得分；这是未实测计算量，不是头的实际耗时，还需计入 transformer attention、投影、候选 embedding 和 graph 折叠。扩大 k 可提高覆盖，却明显增加候选格成本。

用简化独立误差例子说明：两位置 unary 准确率都是 0.8，两者均匹配的概率只有 0.64。关联头可能在边际准确率不变时提高一致性，也可能降低首位置质量而改善后续。因此应观察首次失败位置和累积前缀存活率，而不只看平均位置准确率。

在 selector 实际到达的相同前缀上，要区分覆盖缺失与排序错误：目标 token 不在 top-k，或者在 top-k 却没选中。教师强制条件下的 covered accuracy 使用更容易的样本群体，不等于自反馈 rollout。SpecForge 文档明确区分这些群体，并说明固定记录块的指标是训练诊断，不是随机服务接受率。oracle top-k 长度只是这些块上的覆盖上界，不是服务速度承诺。

## 当前实现与实验

vLLM 提交 `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9` 的文档要求 `LiLiCorrDraftModel`、完整几何配置和头权重，以及 Model Runner V2。训练块包含 anchor，16 位置块通常对应 15 枚推测 token；更长跨度没有训练 slot embedding，缩短则使用前缀，仍需测量。随机 proposal 使用请求温度并发布真实分布。LiLiCorr 专属的 block rejection GPU 验证，以及与自适应验证的组合仍注明待验证；公共框架支持不代表端到端结果。

SGLang 继续使用 `DFLASH`，由检查点的 LiLiCorr architecture 选择实现，不增加独立算法名。文档指出主机序列长度同步和 head eager 回退会消除小幅 selector 收益。这些属于部署成本，与论文的连贯性机制不同。

没有训练权重时，先做训练计划与候选覆盖分析，不声称已经完成服务实验。获得匹配权重后，在相同块宽、target/draft 版本和 sampler 下，比较 plain DFlash、训练 selector 及随机路径选择。训练变体比较还应匹配训练投入。扫描 k，在相同到达前缀上记录覆盖/排序分解，测量候选格与头时间、graph/eager 步数、特征传递、内存、首错位置和实际提交长度。

随后进行未开启 profiler 的客户端 TTFT、输出间隔、完成时间、吞吐、SLO 容量和质量比较。独立检查采样分布，不能用接受率改善代替正确性。继续研究的问题包括：头的增益是否足以支付候选格工作，不同领域怎样选择候选集合，以及量化投影与 graph 折叠如何组合。
## 来源与状态

核对日期为 2026-10-14。

- [LiLiCorr 原论文](https://arxiv.org/html/2608.20530)：候选格、兼容向量、路径选择及训练目标。
- [vLLM 固定文档](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/lilicorr.md)：权重要求、长度约定、proposal 采样与待验证组合。
- [SGLang 固定指南](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx)：公开权重可用性及 graph/backend 条件。
- [SpecForge 训练指南](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/docs/sections/basic_usage/training.md)：DFlash2 selector 目标与覆盖/排序诊断，和 LiLiCorr 训练配方区分。
