<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 多模态生成

[English](README.md) | 简体中文 | [推理知识](../README_zh.md)

按首个可用输出的延迟来源，或限制合格输出吞吐的问题选择条目。

- [同一张图片为什么还要做昂贵预填充？](visual-token-cache_zh.md) 区分精确编码复用与 VLCache 的跨上下文近似视觉 KV 复用，算清动态视觉 token 数。
- [编码 kernel 很快，首 token 为什么仍然慢？](encoder-pipeline-cache_zh.md) 检查微批等待、embedding 生命周期、传输完成及执行重叠，参考 EAServe 的近期自适应组批机制。
- [扩散步骤之间应该缓存什么？](diffusion-feature-cache_zh.md) 比较残差复用、特征预测、AutoTarget 的求解器目标，重点关注少步及非均匀步长。
- [少步生成什么时候意味着换了模型？](few-step-distillation_zh.md) 追踪一致性与因果蒸馏、权重可用性、长时质量，和执行加速分开归因。
- [媒体 token 提前，为什么仍不能提前播放？](streaming-audio-video_zh.md) 顺着 codec 分块、lookahead、波形/视频解码、传输与客户端缓冲定位问题。
- [混合分辨率或 adapter 为什么难以高效组批？](heterogeneous-batching_zh.md) 区分形状 packing 与兼容性感知调度，保留各 pipeline 的 step contract。
