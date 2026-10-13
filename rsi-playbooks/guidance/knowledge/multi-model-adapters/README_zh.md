<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 多模型与适配器

[English](README.md) | 简体中文 | [推理知识](../README_zh.md)

先区分共享边界：LoRA adapter 共享基础模型计算；不同完整模型主要共享设备容量与执行时间。

- [低 rank 更新或打包 QKV 为什么仍然慢？](grouped-lora-kernels_zh.md) 检查当前 grouped shrink/expand、不等宽 launch grid、仍未合并的 split-K 提案及其精度和硬件约束。
- [总吞吐提高，为什么部分租户仍错过期限？](tenant-aware-scheduling_zh.md) 比较 rank 感知放置、多 SLO slack 调度、base/LoRA 重叠，区分 token 生成与释放。
- [Adapter miss 为什么会突然放大尾延迟？](elastic-adapter-residency_zh.md) 追踪 slot 生命周期、热切换、KV 内存竞争及 CLIMB 的驻留感知入口，保留公开 artifact 的执行缺口。
- [一个模型空闲，为什么另一个仍拿不到内存？](shared-model-execution_zh.md) 研究 Prism OSDI 2026 ballooning、当前 kvcached 支持和激活干扰；共置不意味着共享 KV 语义或基础 GEMM。

已有多 LoRA 组批、加载和弹性内存是复用起点，不是新的功能提案。每篇给出近期研究或具体剩余执行问题、权重与实现可用性，以及能区分原因的服务实验。来源核对截止到 2026-10-14。
