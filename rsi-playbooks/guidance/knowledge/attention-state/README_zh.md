<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 注意力与循环状态

[English](README.md) | 简体中文

根据注意力执行中的主要成本，或阻止模型状态安全复用的问题，选择对应条目。

- [稠密注意力流水线](dense-attention-pipelines_zh.md)：矩阵乘法足够快之后，识别 Blackwell 的 softmax 与重缩放瓶颈，研究实际形状分派和混合流量干扰。
- [MLA 缓存布局与 decode 调度](mla-cache-layouts_zh.md)：区分模型特定的量化格式、稀疏读取、分片归约及 FlashMLA 兼容边界。
- [稀疏索引器路由](sparse-indexer-routing_zh.md)：研究 sparse MLA 之后仍存在的历史 token 打分成本，理解 MISA 的 head 路由与近似选择取舍。
- [按通道遗忘的循环状态](channel-gated-recurrent-state_zh.md)：理解 KDA 的 decay/update 顺序、分块并行 prefill、循环 decode 与状态布局交接。
- [混合模型前缀检查点](hybrid-prefix-checkpoints_zh.md)：让 attention KV、循环与卷积状态在同一可复用边界恢复，权衡快照复制、重放和容量。
- [循环 decode 与 speculative replay](recurrent-speculation-replay_zh.md)：摊薄循环状态写回，不保存中间矩阵快照也能提交 accepted token，同时保持 flush 和导出语义。

每篇区分上游已有机制与仍值得研究的问题。来源和集成状态核对于 2026-10-14。

返回[推理知识库](../README_zh.md)。
