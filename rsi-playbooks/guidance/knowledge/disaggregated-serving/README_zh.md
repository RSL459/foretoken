<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 分离式推理服务

[English](README.md) | 简体中文

按节省的工作、需要传输的状态和延迟预算选择执行边界，而不是把独立部署的 worker 数量当作优化目标。

- P/D 分离何时划算？[减少预填充与解码干扰：按缓存和负载选择阶段分离](reduce-prefill-decode-interference-through-conditional-stage-separation_zh.md)比较干扰消除收益与传输、排队和角色切换成本，区分条件路由与 worker 转换。
- 多个 attention worker 能否高效共用专家池？[提高专家批次利用率：Attention–FFN 分离与工作汇聚](increase-expert-batch-utilization-through-attention-ffn-disaggregation_zh.md)解释 FastAFD 的微批执行、显存收益、集合通信顺序及硬件相关资源比例。
- 为什么单个阶段加速后服务没有变快？[避免流水线积压：联合分配各阶段容量](prevent-pipeline-backlogs-through-joint-stage-capacity-allocation_zh.md)围绕端到端关键路径分配 encoder、prefill、传输和 decode 容量。
- 链路很快，KV 传输为什么仍然阻塞？[诊断 KV 交接停顿：汇聚传输剖析](diagnose-kv-handoff-stalls-through-fan-in-transfer-profiling_zh.md)计算 KV 字节数，分析汇聚流量、主机中转、布局转换和完成通知生命周期。
- 每个阶段应该使用哪类加速器？[降低服务成本：基于实测容量的异构阶段放置](reduce-serving-cost-through-profiled-heterogeneous-stage-placement_zh.md)按满足 SLO 的有效吞吐和总成本比较可执行的阶段／设备组合。

容量控制、缓存感知放置和实例退役见[扩缩容与放置](../autoscaling-placement/README_zh.md)。Encoder 执行和多模态输入细节见[多模态知识](../multimodal-generation/README_zh.md)。

[返回推理知识](../README_zh.md)
