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

## 证据范围

实现核对日期为 2026-10-14。

核对快照：

- Dynamo：`b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd`，2026-10-13。
- llm-d：`277b34d062ff954435cf8b1b05efbd75090cf788`；inference scheduler：`5253f55516f496129248766d1e4b745daba68887`，2026-10-13。
- AIBrix：`d0500b0399cf35ad0bf95d073faa83c23308f463`，2026-10-13。
- Production Stack：`4e076e8de3698a3729b575e3a5ade65ffbb929cf`，2026-10-07。
- FastAFD：`3c7161949310b6d59d6b4cf9bf997a4935c8113b`，2026-07-08。
- Foretoken：`e6ae3df6d02a72f4bbec3050c4291c1489c1bc07`。

[返回推理知识](../README_zh.md)
