<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 预测负载路由与观测延迟

[English](predictive-load-routing.md) | 简体中文

队列长度说明有多少请求等待，却不能说明新请求前面还有多少工作。路由需要估计请求给各候选增加的延迟，并及时计入已经 dispatch、尚未进入引擎指标的工作。

## 当前路由器已做哪些估计

Dynamo 当前 selector 结合活跃 prefill token、缓存 overlap、decode 成本与活跃请求压力，并非只选请求数最少的实例。Production Stack 在完成 tokenization 和缓存查询后使用当时的路由监测统计，但负载仍是 in-prefill 加 in-decoding 请求数。AIBrix 除 prefix/load 混合外已经提供 Preble 策略。

llm-d 当前 predicted-latency producer 和 scorer 更进一步：XGBoost sidecar 预测逐 endpoint TTFT/TPOT，请求生命周期 hook 追踪 in-flight 工作，endpoint attributes 保存预测及 SLO headroom。因此 prediction-driven routing 已是现有 upstream 能力，不能当作假想新功能。

## 预测工作量而非只数请求

A 排着三个 16K-token 未缓存 prompt，B 排着十个 128-token prompt。Queue depth 偏好 A，prefill 工作量却可能偏好 B。若新请求在 A 有长前缀命中，增量未缓存工作又可能反转排序。Preble 根据测量得到的 token-dependent 函数估算执行成本，并考虑近期负载及驱逐代价；DualMap 在双候选架构中用 pending prefill token 估计首 token 压力。

可用 `finish_estimate = current_wait_estimate + incremental_service_estimate` 分析。输入至少要区分未缓存输入、当前上下文长度、decode 人数与 worker 配置。校准绑定具体模型、dtype、backend、拓扑与并行配置。量化、kernel 或 graph 设置改变后，原先训练的预测器可能出现系统性偏差。

指标延迟是另一种问题：两次引擎采样间到达十个请求，可能都选择上次看起来空闲的 endpoint。即时 dispatch reservation 能代表尚不可见的工作，再由同一个生命周期 owner 对照执行或完成状态进行归并，并在错误、取消时释放。若测量负载已包含某个 reservation，却把两者相加，就会重复计量；纠正需要明确观测边界，而不是再建一套独立全局 counter。

## 核对预测的真实语义

llm-d producer 按 `SLO - predicted_latency` 及可配置 buffer factor 计算 headroom。当前 scorer 先按 headroom 分组；所有 endpoint 都缺预测时，使用 KV 可用量、队列大小和前缀命中的组合 fallback。若预测都违反目标，会在存在 idle 候选时优先它们，否则选择较轻的 deficit 类别，并不必然拒绝请求。

缺失预测的 endpoint 还能以零 headroom 留在 nonnegative 组。部分 sidecar 失败与全部缺失的 fallback 并不等价，实验应单独区分。Producer 文档还说明，非流式 TTFT 标签采到 EOS，实际相当于端到端延迟，TPOT 则被中和；不能把流式与非流式标签混为同一种首 token 观测。

## 职责与适用条件

引擎发布执行与缓存观测。Foretoken 请求层负责选择、dispatch reservation 与生命周期释放；新增 counter 前，应先检查现有 request ledger 的职责。集群编排负责容量变化。预测服务可以是外部 adapter，但预测缺失或不准时如何选择，仍归路由层所有。

请求形状差异大、长期有竞争时预测更有价值。低负载下，预测调用延迟可能超过收益。突发、状态陈旧与 workload 改变时，需要评估排序正确性，不只是回归平均误差；平均误差很低的模型也可能为 deadline 紧迫请求选错实例。

## 实验与剩余问题

重放带时间戳的短/长输入、缓存热续问和突发区间，在同一候选集合上比较现有工作量/请求数评分与预测器。分别改变指标采样延迟、sidecar 响应延迟和部分预测缺失，不要同时改三项。

记录预测与实际 TTFT/TPOT、候选两两排序错误、排队时长、路由开销、逐 worker 分配、p99 token 间隔，以及面向所有到达请求的 SLO-qualified completions。预测应与同一请求的真实观测对应，而不是拿无关 endpoint 均值比较。检查 outstanding work 时覆盖完成与取消路径。

剩余空间是执行条件变化时的可靠校准与状态归并。新预测器应与经过合理调参的现有工作量 scorer 比较，而不只与请求数评分比较。

## 来源

核查日期：2026-10-14。

- [Preble v2，2024-10-03](https://arxiv.org/html/2407.00023v2)及 [DualMap v1，2026-02-06](https://arxiv.org/html/2602.06502v1)：请求路由边界的成本预测。
- [llm-d predicted-latency producer，commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/requestcontrol/dataproducer/predictedlatency/README.md)：生命周期 hook 与标签语义。
- [llm-d latency scorer，同一 revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/scorer/latency/plugin.go)：实际分组与 fallback。
- [Dynamo selector，commit 7708f041](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kv-router/src/scheduling/selector/reference.rs)。
- [Production Stack routing，commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py)。
- [AIBrix 路由文档，commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/docs/source/features/gateway-routing/prefix-cache-aware-routing.rst)。
