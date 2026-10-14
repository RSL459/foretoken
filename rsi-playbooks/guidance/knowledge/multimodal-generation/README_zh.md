<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 多模态生成

[English](README.md) | 简体中文 | [推理知识](../README_zh.md)

按首个可用输出的延迟来源，或限制合格输出吞吐的问题选择条目。

- [减少视觉预填充：编码缓存与选择性 KV 复用](reduce-visual-prefill-through-encoder-and-kv-reuse_zh.md) 区分精确编码复用与 VLCache 的跨上下文近似视觉 KV 复用，算清动态视觉 token 数。
- [降低多模态首 token 延迟：自适应编码微批](reduce-multimodal-ttft-through-adaptive-encoder-microbatching_zh.md) 检查微批等待、embedding 生命周期、传输完成及执行重叠，参考 EAServe 的近期自适应组批机制。
- [减少扩散计算：特征复用与求解器目标缓存](reduce-diffusion-compute-through-feature-and-solver-target-reuse_zh.md) 比较残差复用、特征预测、AutoTarget 的求解器目标，重点关注少步及非均匀步长。
- [蒸馏少步生成模型：一致性训练与分布匹配](distill-few-step-generation-through-consistency-and-distribution-matching_zh.md) 追踪一致性与因果蒸馏、权重可用性、长时质量，和执行加速分开归因。
- [降低首个可播放媒体延迟：分块解码与交付](reduce-first-media-latency-through-chunked-decoding-and-delivery_zh.md) 顺着 codec 分块、lookahead、波形/视频解码、传输与客户端缓冲定位问题。
- [减少多模态填充与等待：兼容性感知组批](reduce-multimodal-padding-and-waiting-through-compatible-batching_zh.md) 区分形状 packing 与兼容性感知调度，保留各 pipeline 的 step contract。
