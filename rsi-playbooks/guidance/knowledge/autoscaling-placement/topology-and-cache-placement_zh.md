<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 拓扑与缓存放置

[English](topology-and-cache-placement.md) | 简体中文

## 问题与机制

新增副本可能增加算力，却降低缓存复用或压满共享缓存链路。Placement 决定容量和状态在哪里，routing 决定哪些请求使用它们。缓存索引回答哪里报告了可复用状态，不会自行放置 worker、预留带宽或搬运数据。

对每个可行位置估计 `T = queue + restore + uncached_prefill + decode`。GPU 本地命中、主存恢复和远端共享缓存的代价不同。先确认 checkpoint、位置语义、dtype、connector 布局允许复用，再比较节省的计算与状态移动／竞争。

例如可从远端恢复 3 GiB 前缀 KV，或在本地用 40 ms 重算同一段前缀。20 GB/s 有效路径至少需约 161 ms，还未计 setup 与排队；最长命中策略会选错。若重算这段前缀需 500 ms，恢复可能更合适。两种路径随后都要处理未缓存后缀。加权命中分数可以表示偏好，却不是经过校准的传输时间估计。

放置还影响未来状态分布。把热前缀集中在一个域能强化亲和性，也会造成 fan-in 热点和故障集中。复制降低竞争，却花费显存与预热网络。独立冷副本可能分散计算，同时不断重复生成相同前缀。固定 GPU 预算下，一项放置改善某个模型，也可能把另一个模型挤出 SLO 下界。

## 硬件、模型与成本

拓扑包括 GPU–NIC 亲和性、NVLink/NVSwitch 域、机架链路、主机 NUMA 和共享存储带宽。Dense BF16 全注意力 KV 与 MLA 状态的大小不同，混合模型还涉及多种状态。FP8 权重不意味着远端 KV 便宜；不同 TP 布局在恢复前可能要 gather 或复制。

应计缓存预热字节、重复权重、共享存储容量和退役损失。节点已有权重缓存能加快启动，却不代表已有暖请求 KV，这是不同收益。静态 quota 准入同样不保证获准设备靠近目标缓存或伙伴阶段。

## 当前实现与证据

核对日期为 2026-10-14。llm-d 的[cost-aware-memory 实现](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/kvcache/kvblock/cost_aware_memory.go)通过有界存储管理估计索引内存成本。`DeviceTier` 参与索引内存记账，lookup 查找可用前缀；worker 分配和数据搬运由各自的 owner 负责。

Production Stack 的[路由代码](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py)已有基于 LMCache 的前缀查询和 load/cache 评分，会刷新存活 endpoint／instance 映射；这是请求路由，不是自动缓存迁移。llm-d 的[Kueue 指南](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/kueue-rebalancing/README.md)在 HPA 下提供模型 quota 下界、借用与抢占，不是缓存局部性优化。

Foretoken 的[路由 owner](../../../../data-plane/frontend/src/router/README_zh.md)已区分 GPU-local credit 与恢复后缀，`restoreWeight` 默认 0.5，并平衡 per-rank 请求压力。文档明确这些权重只是偏好，不是传输估计；Encoder/Decode 只用负载。

2026 年 [AFD 设计空间研究](https://arxiv.org/html/2605.28302v1)建模 B200、FP8 MoE 在 scale-up／scale-out 链路上放置 P/D 伙伴的差异。其网络估计适合比较伙伴放置与共享链路竞争。

## 有区分力的实验与剩余问题

先在固定放置图上，用实测链路服务曲线重放路由，独立改变热前缀集中度、恢复带宽和缓存容量。比较 local-only、最长命中、load-only 和延迟成本估计。加入并发 restore，避免用孤立传输的准确预测掩盖共享拥塞。

真实多轮服务保持内容和 arrival schedule 一致，在相同硬件预算下比较集中与分散放置。记录本地／远端命中、恢复字节、查询延迟、TTFT、ready 容量、共享链路利用率和扩缩后预热。先固定路由只改放置，再固定放置只改路由，才能归因。滞后索引、尾延迟感知联合放置、考虑 eviction 的扩缩容仍待研究。缓存内部见[KV 缓存](../kv-cache/README_zh.md)，阶段约束见[分离式服务](../disaggregated-serving/README_zh.md)。

[返回扩缩容与放置](README_zh.md)
