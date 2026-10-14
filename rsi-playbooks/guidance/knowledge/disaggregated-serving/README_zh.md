<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 分离式推理服务

[English](README.md) | 简体中文

按节省的工作、需要传输的状态和延迟预算选择执行边界，而不是把独立部署的 worker 数量当作优化目标。

- P/D 分离何时划算？[P/D 成本与动态分配](pd-cost-and-dynamic-allocation_zh.md)比较干扰消除收益与传输、排队和角色切换成本，区分条件路由与 worker 转换。
- 多个 attention worker 能否高效共用专家池？[Attention–FFN 分离](attention-ffn-disaggregation_zh.md)解释 FastAFD 的微批执行、显存收益、集合通信顺序及硬件相关资源比例。
- 为什么单个阶段加速后服务没有变快？[多阶段资源平衡](multistage-resource-balance_zh.md)围绕端到端关键路径分配 encoder、prefill、传输和 decode 容量。
- 链路很快，KV 传输为什么仍然阻塞？[传输与网络瓶颈](transfer-network-bottlenecks_zh.md)计算 KV 字节数，分析汇聚流量、主机中转、布局转换和完成通知生命周期。
- 每个阶段应该使用哪类加速器？[异构阶段放置](heterogeneous-stage-placement_zh.md)按满足 SLO 的有效吞吐和总成本比较可执行的阶段／设备组合。

容量控制、缓存感知放置和实例退役见[扩缩容与放置](../autoscaling-placement/README_zh.md)。Encoder 执行和多模态输入细节见[多模态知识](../multimodal-generation/README_zh.md)。

[返回推理知识](../README_zh.md)
