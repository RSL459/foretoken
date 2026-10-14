<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 扩缩容与放置

[English](README.md) | 简体中文

副本建议只有与实际硬件、启动延迟、路由状态和退役过程配合，才能变成可用容量。

- 当前负载需要多少副本才能满足延迟目标？[估算满足 SLO 的容量：校准服务曲线](size-slo-capacity-through-calibrated-service-curves_zh.md)结合校准过的服务模型和实时延迟反馈，区分均值预测与分位数目标。
- 为什么扩容总在突发结束后才生效？[提前准备所需容量：按启动延迟预测 token 需求](anticipate-capacity-demand-through-startup-aware-token-forecasting_zh.md)让预测跨度匹配执行延迟，并计入已经启动的容量。
- 请求数相同，为什么所需 GPU 容量不同？[确定副本数量：未命中 token 工作量与 KV 压力](size-replicas-through-uncached-token-and-kv-pressure_zh.md)分开未命中预填充工作、解码活动、KV 占用、排队需求与模型相对服务缺口。
- 缓存和链路共享时，新容量应该放在哪里？[降低请求延迟：拓扑感知的缓存与副本放置](reduce-request-latency-through-topology-aware-cache-placement_zh.md)联合评估放置和路由，纳入竞争与暖状态丢失。
- 如何移除繁忙 worker 而不丢失正在生成的回答？[保持在途生成连续：排空与状态交接](preserve-active-generations-through-draining-and-state-handoff_zh.md)区分路由撤回、自然完成、请求迁移和共享缓存清理。

阶段划分与传输成本见[分离式推理服务](../disaggregated-serving/README_zh.md)，其他机制见[推理知识](../README_zh.md)。

[返回推理知识](../README_zh.md)
