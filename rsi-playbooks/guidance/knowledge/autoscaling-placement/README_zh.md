<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 扩缩容与放置

[English](README.md) | 简体中文

副本建议只有与实际硬件、启动延迟、路由状态和退役过程配合，才能变成可用容量。

- 当前负载需要多少副本才能满足延迟目标？[SLO 容量估计](slo-capacity-estimation_zh.md)结合校准过的服务模型和实时延迟反馈，不把均值预测误当成分位数保证。
- 为什么扩容总在突发结束后才生效？[预测扩容与冷启动](predictive-scaling-and-cold-start_zh.md)让预测跨度匹配执行延迟，并计入已经启动的容量。
- 请求数相同，为什么所需 GPU 容量不同？[Token 负载状态](token-load-state_zh.md)分开未命中预填充工作、解码活动、KV 占用、排队需求与模型相对服务缺口。
- 缓存和链路共享时，新容量应该放在哪里？[拓扑与缓存放置](topology-and-cache-placement_zh.md)联合评估放置和路由，纳入竞争与暖状态丢失。
- 如何移除繁忙 worker 而不丢失正在生成的回答？[排空与状态迁移](drain-and-state-migration_zh.md)区分路由撤回、自然完成、请求迁移和共享缓存清理。

阶段划分与传输成本见[分离式推理服务](../disaggregated-serving/README_zh.md)，其他机制见[推理知识](../README_zh.md)。

## 证据范围

实现核对日期为 2026-10-14。

核对快照为 Dynamo `b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd`、llm-d `277b34d062ff954435cf8b1b05efbd75090cf788`、llm-d inference scheduler `5253f55516f496129248766d1e4b745daba68887`、AIBrix `d0500b0399cf35ad0bf95d073faa83c23308f463`（均为 2026-10-13），Production Stack `4e076e8de3698a3729b575e3a5ade65ffbb929cf`（2026-10-07），以及 Foretoken `e6ae3df6d02a72f4bbec3050c4291c1489c1bc07`。

[返回推理知识](../README_zh.md)
