<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 多模型与适配器

[English](README.md) | 简体中文 | [推理知识](../README_zh.md)

先区分共享边界：LoRA adapter 共享基础模型计算；不同完整模型主要共享设备容量与执行时间。

- [加速 LoRA 推理：紧凑分块与 split-K 归约](accelerate-lora-inference-with-compact-tiles-and-split-k_zh.md) 检查当前 grouped shrink/expand、不等宽 launch grid、已合并的可选 split-K 及其精度和硬件约束。
- [满足适配器请求期限：按 rank 与剩余时间调度](meet-adapter-deadlines-through-rank-and-slack-aware-scheduling_zh.md) 比较 rank 感知放置、多 SLO slack 调度、base/LoRA 重叠，区分 token 生成与释放。
- [减少适配器换入换出抖动：驻留感知请求派发](reduce-adapter-thrashing-through-residency-aware-request-dispatch_zh.md) 追踪 slot 生命周期、热切换、KV 内存竞争及 CLIMB 的驻留感知入口，保留公开 artifact 的执行缺口。
- [多模型共享 GPU 容量：按需伸缩物理内存](share-gpu-capacity-through-multi-model-memory-ballooning_zh.md) 研究 Prism OSDI 2026 ballooning、当前 kvcached 支持和激活干扰；共置不意味着共享 KV 语义或基础 GEMM。
