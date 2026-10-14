<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Token 负载状态

[English](token-load-state.md) | 简体中文

## 问题与机制

十个 256-token prompt 和十个 32K prompt 的队长相同，工作量与 KV 驻留却不同。即使 token 数相同，前缀复用或流量集中到某个 DP rank 也会改变所需容量。决策需要状态向量，而不是单一请求计数替代量。

有用维度包括未命中的排队 prefill token、已调度 decode 上下文、排队 decode 上下文需求、KV 容量／占用、active 请求、ready worker 和实测速率。单位要明确：排队 token 除以校准的 prefill token/s，是 backlog 秒数；驻留上下文除以 KV token 容量，是显存压力。两者都不自动等于 TTFT 预测。

例如两个等容量 rank 的 KV 压力为 0.95 和 0.15，平均 0.55 看似宽裕，热 rank 却可能停止接收请求。新增副本只有在路由重新分配时才可能有效。可复用前缀占据缓存，也不代表等量 prefill 计算。需要考虑未命中后缀和共享 block，不能把每个请求原始长度不加区分地求和。

多模型之间，原始 token/s 不代表可比服务。2026 年 TRE 论文提出 `TSS_raw = (w_p*r_prefill + r_decode)/(active + w_q*waiting)`，再把平滑值除以模型／SLO 对应的健康边界 θ。其中 r_prefill、r_decode 是同一窗口内实际处理的 token/s，active、waiting 是请求数，w_p、w_q 分别为无量纲的 prefill 服务权重与等待需求权重。TSS_raw 与 θ 的单位均为每个加权未完成请求获得的加权 token/s。归一化值无量纲，小于 1 表示低于该校准的健康服务水平。权重与阈值依赖负载和 runtime。

## 硬件、dtype 与成本

KV 压力应遵循全注意力、MLA、滑动窗口或混合状态的实际分配。权重和缓存 dtype 不同；BF16 KV 换成 FP8 会改变容量并可能需要质量验证，仅改权重精度可能加快计算却不减少上下文驻留。TP/DP 布局决定哪些计数是重复、哪些是分片。

准入时未知输出长度。未来 decode 工作估计可能因早 EOS 高估，也可能低估长生成。Router 在途工作、scheduler 排队、真实 cache 分配有不同生命周期。采集／同步成本要与它改善的决策比较；细节很多但滞后的状态，可能不如粗粒度实时信号。

## 公开实现与当前范围

核对日期为 2026-10-14。Foretoken 的[token-load 算法](../../../../control-plane/internal/autoscaling/algorithm/decision/token_load.go)逐 engine 评估。Prefill preset 按 context length 归一化队列 token，自定义 `load` 使用绝对 token；decode 以已调度加排队上下文除以 KV 容量，aggregate 再加 queued prefill。一个热 engine 可请求增加 Group；缩容检查所有 engine，并估计重新分配后的压力。[指南](../../../../docs/autoscaling_zh.md)限定单一 full-attention cache group、PCP/DCP=1，encoder pool 及观测不可用、不完整或过期的目标，在配置的副本上下界内保持现有容量。

llm-d 的[在途 producer](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/requestcontrol/dataproducer/inflightload/producer.go)扣除前缀命中，在 stream start 释放 prefill 贡献，stream end／TTL 淘汰移除请求，endpoint 删除时清理指标序列。[P/D prefill trigger](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/keda-epp-token-aware/pd-disaggregation/base/prefill-scaledobject.yaml)把总 backlog token 除以实测吞吐；[decode trigger](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/keda-epp-token-aware/pd-disaggregation/base/decode-scaledobject.yaml)求和 decode Pod 的 KV fraction。

[TRE](https://arxiv.org/html/2609.29160v1)提供面向 colocated P/D 和校准服务阈值的 Kubernetes hot-switch 研究原型及[公开实现](https://github.com/zxzx9898/Token-service-share_Rebalancing_Engine)。

## 实验与剩余问题

先固定请求数，改变长度、命中和 rank 偏斜，在重放模型中比较 queue-only、总 token 压力、per-rank 状态。加入已删除 endpoint 计数和 early EOS，暴露滞后估计。

真实服务同时采集 router 估计、scheduler 状态和 cache 占用，比较它们与实际完成 token／驻留的误差，把扩缩决策关联到 SLO goodput 和 ready 容量。测试请求率固定但长度分布改变。输出长度不确定性、混合状态需求语义和跨模型服务校准仍待研究。快速决策见[路由与准入](../routing-admission/README_zh.md)，不属于 autoscaler 生命周期。

[返回扩缩容与放置](README_zh.md)
