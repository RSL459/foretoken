<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 少步生成改变的是训练后的模型

[English](few-step-distillation.md) | 简体中文 | [多模态生成](README_zh.md)

## 先分开模型压缩与执行加速

把扩散采样从多次执行降到少数几次，不等于原来的 kernel 变快。蒸馏训练另一个预测器，用更少步复现轨迹或输出分布。权重、solver、guidance、训练目标变化后，多样性与提示遵循都可能改变，哪怕示例看起来接近。服务比较必须保留这些差异，不能把换成蒸馏模型描述为无损优化。

LCM 与 LCM-LoRA 是一致性模型的历史基础。较新的流式视频还需要解决另一问题：训练时看到真实或教师生成的历史，推理时却消费自身不完美的历史。公开 NVIDIA rCM 仓库中的 Causal-rCM 提供了可研究的 2026 实现。已有少步模型是起点；研究空间在于训练假设与服务条件能否适应目标负载。

## 从训练到一次推理

教师给出高质量去噪轨迹。一致性目标训练学生，把同一轨迹上的不同噪声状态映射到共同的去噪结果，因此推理可以跨大步。无分类器引导可以在蒸馏中融入，学生不一定继续采用教师原来的 guidance scale 或采样配方。LCM-LoRA 将蒸馏更新表示成与指定基础模型兼容的低秩权重，不是适配所有扩散 checkpoint 的通用 adapter。

因果视频先用少数去噪执行生成第一块，保存允许访问的历史，再据此生成下一块。如果训练始终提供干净历史、推理却使用学生生成的历史，条件分布就会变化。Causal-rCM 将 teacher-forcing 的一致性训练与 self-forcing 的 on-policy 分布匹配蒸馏结合。后者让学生实际展开，并针对它自己会遇到的状态训练；前者提供互补的监督轨迹。通用 rCM 配方建议依次进行 dCM warmup、sCM、DMD with sCM；因果指南则采用 teacher-forcing CM 后接 self-forcing DMD 的流程。

因果指南先将双向 Wan checkpoint 适配为因果教师，再蒸馏学生，最后用 self-forcing DMD 精修。最后阶段使用三类扩散网络：可训练学生、提供真实分布 score 的冻结双向教师，以及估计学生分布的可训练 fake-score 网络。两个 score 的差异指导学生逼近教师分布，fake-score 网络则用学生样本训练。推理只保留学生、文本编码器和 VAE。

普通分块推理在每块后还执行一次零噪声的干净上下文计算；复用最后噪声状态可以省这次执行，但必须匹配 noisy-context 训练与分块设置。因此不能只数去噪步，还要数上下文执行。

总时间可写为 T = N_student T_DiT + T_context + T_text + T_VAE + T_delivery。N_student 是去噪执行次数，T_DiT 是单次平均耗时，T_context 包含额外历史上下文执行。减少 N_student 只优化其中一项。四步生成可能让 VAE 或传输变成新瓶颈；换模型与改 kernel 必须分开归因。

## 权重、硬件与质量

rCM 资产说明链接到 Wan2.1 T2V 1.3B／14B 教师、VAE 和 umT5。训练代码与配置公开；指南列出 rCM/Causal-rCM checkpoint 名称，但没有完整的可下载学生权重清单。少步推理需要取得训练好的学生，或复现其训练，只有 Wan 教师权重还不够。

其环境涉及 CUDA、PyTorch、FlashAttention、FSDP2 和可选 Ulysses context parallelism，这些是特定实现依赖，不代表跨硬件通用。记录实际 BF16/FP16 训练与推理配置；降低推理精度是额外质量变量。LCM_Dreamshaper_v7 示例采用 FP32，并说明 FP16 可以省内存，但可能降低图像质量。

分布匹配可能改善真实感，却不保证每个提示或多样性模式都保留。长时间自回归展开可能漂移、重复、换主体，即使短片得分很好。适合的约束通常是可接受质量工作点，不是与教师逐样本完全一致。

## 区分收益来源的实验

先比较教师及其正常 sampler，与已发布或复现的学生及其少步 sampler；再保持学生权重与 sampler 不变优化执行；若加缓存，作为第三项变化。记录 prompt、在有意义时匹配的 seed、分辨率、视频时长、negative prompt 与 guidance 语义。

测量首个可用帧延迟、完整视频延迟、稳定生成帧率、GPU 内存、达到质量要求的成功输出吞吐，以及每个合格视频秒成本。质量覆盖提示遵循、主体一致、运动、跨 seed 多样性和长时漂移。如果假设是 self-forcing 改善展开稳定性，就应在相同推理预算下比较两种训练方式；短片延迟结果无法回答这一问题。

## 来源与核对状态

核对日期：2026-10-14。

- [NVIDIA rCM](https://github.com/NVlabs/rcm/tree/ed3cb14dd936f92cdc9f9381af7369991509b41f)：README、资产说明与因果训练入口，版本为 2026-06-25 的 `ed3cb14`。
- [Causal-rCM 指南](https://github.com/NVlabs/rcm/blob/ed3cb14dd936f92cdc9f9381af7369991509b41f/Causal_rCM.md)：因果训练和推理入口，具体可用性取决于模型与配置。
- [LCM 作者仓库](https://github.com/luosiallen/latent-consistency-model)：训练与公开 LCM/LCM-LoRA 模型说明。
