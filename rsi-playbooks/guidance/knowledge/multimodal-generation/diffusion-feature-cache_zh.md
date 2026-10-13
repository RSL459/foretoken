<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 扩散缓存：特征复用、预测与求解器目标

[English](diffusion-feature-cache.md) | 简体中文 | [多模态生成](README_zh.md)

## 缓存什么，比“开不开缓存”更重要

扩散 transformer 会多次计算相近的 latent。跳过部分执行可以不用训练新模型就加速，但会改变数值轨迹。TeaCache、TaylorSeer 分别提供两个基础思路：判断残差何时还能复用，或预测特征而不是直接保持旧值。2026 年 10 月的 AutoTarget 提出更近的问题：少步模型应该缓存哪种面向求解器的量？这些都是近似方法，不是无损 kernel 融合。

当前 vLLM-Omni 已有 cache-dit 集成文档，应复用其设施，不把基本缓存再列为新能力。也不能由此推断所有论文方法或执行模式均受支持：本次核对的执行模式文档明确表示 step execution 不支持扩散 cache backend。

## 一个去噪区间如何执行

TeaCache 在锚点执行完整 transformer，保存残差。后续步计算经过 timestep 调制的输入相对 L1 变化，以拟合多项式估计昂贵计算的变化并累加。未超过阈值时，把旧残差加到当前输入；超过后重新计算并刷新缓存。廉价指标只是代理，不同模型需要不同校准。

TaylorSeer 保存完整执行得到的特征及有限差分，在锚点间用截断 Taylor 展开预测，例如 F_hat(t+delta)=F(t)+delta F'(t)+delta² F''(t)/2。导数来自采样特征的估计，不是对整个 sampler 自动求导。高阶预测可改善外推，也增加缓存状态，遇到特征突变时仍可能失效。

AutoTarget 把目标放到求解器接口。线性流满足 x_t=(1-t)c+t e、v=e-c，因此锚点提供 c=x_a-t_a v_a、e=x_a+(1-t_a)v_a。在论文规定的转换条件下，确定性 Euler 复用 velocity、clean endpoint 或 noise endpoint，会得到相同的锚点间轨迹。但缓存位移 h_a v_a 并不等价：下一步区间为 h_j 时，误差与 (h_j-h_a)v_a 成正比。只写缓存变量名，无法定义完整语义。

AutoTarget 校准时记录精确 solver 状态，在相同锚点与复用状态下比较合法目标，再通过固定 VAE 的 RGB 误差排序；最佳候选差距太小时放弃选择。当前 Omni 缓存指南不建议对少步蒸馏模型使用 TaylorSeer。AutoTarget 选择求解器目标是另一机制，不能据此推断 TaylorSeer 已适合这些 pipeline。

## 权重、硬件与质量代价

TeaCache、TaylorSeer 使用已有图像或视频扩散权重，不重训模型。AutoTarget 公开代码提供 FLUX、PixArt-LCM、HunyuanVideo 的转换与选择逻辑，不发布新权重。实验必须配套取得 checkpoint、VAE、文本编码器与 scheduler。更换分辨率、guidance、dtype 或 solver 后继续使用旧阈值，是需要重新验证的假设。

FP16/BF16 特征也会累积预测误差；FP8 缓存量化又是另一项近似，不能一起归因给缓存策略。NVIDIA 参考实现不证明其他设备可用。相对参考图片的 PSNR 可帮助诊断轨迹偏移，但提示遵循、文字生成、运动和多样性需要分别评分。特征变化小，不代表语义变化不重要。

## 如何比较才有区分力

固定权重、prompt、seed、分辨率、guidance、dtype 和 solver，比较无缓存、残差复用、特征预测、solver 目标复用，并匹配完整 transformer 执行次数。分别使用均匀与非均匀步长，区分目标语义优势和“只是多算几次”。少步模型应独立比较，因为省掉一次就是轨迹的重要部分。

记录 transformer 调用次数及耗时、预测与归约时间、VAE 时间、峰值缓存、服务总延迟、排队、满足质量及延迟目标的图片数或视频秒数，以及失败请求。覆盖不同提示类型和运动变化，检查实际输出。匹配调用次数后收益消失，说明原因在刷新频率；只有非均匀区间出现差异，则应直接检查位移转换。

## 来源与核对状态

核对日期：2026-10-14。

- [TeaCache，arXiv:2411.19108v1](https://arxiv.org/html/2411.19108v1) 与[作者代码](https://github.com/ali-vilab/TeaCache)：残差与累积代理机制，仅作基础。
- [TaylorSeer，arXiv:2503.06923v1](https://arxiv.org/html/2503.06923v1) 与[作者代码](https://github.com/Shenyi-Z/TaylorSeer)：预测递推及模型入口。
- [AutoTarget，arXiv:2610.03577v1](https://arxiv.org/html/2610.03577v1)：2026-10-02 提交，方法；[公开实现](https://github.com/wali1024-offical/AutoTarget/tree/e91a428b8bbc37a6661576a182e39e94e3cc55dd)版本为 2026-10-01 的 `e91a428`。
- [Omni 执行模式](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/diffusion/execution_modes/)与 [cache-dit 文档](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/user_guide/diffusion/cache_acceleration/cache_dit.md)：源码路径版本为 2026-10-13 的 `37f094a`；`v0.30.0` 发布于 2026-09-25，main 状态不能直接当作 release 状态。
