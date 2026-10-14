<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 引擎调度

[English](README.md) | 简体中文

决定每轮推理执行哪些工作，同时兼顾 prefill 进度、token 交付、KV 容量与共享服务。

- [通过 Token 预算控制预填充分块，减少解码停顿](limit-decode-stalls-through-budgeted-prefill-chunks_zh.md)：在满足 token 交付目标时，一轮 decode 还能容纳多少 prefill？
- [通过批次工作量与解码频率控制提高 SLO 达标率](improve-slo-attainment-batch-sizing-and-decode-cadence_zh.md)：不同 TTFT/TPOT 目标的请求何时应获得不同执行频率？
- [通过内存感知的运行集合选择避免 KV 抢占与重算抖动](avoid-kv-thrashing-through-memory-aware-batch-selection_zh.md)：起初可执行的运行集合为何后来反复抢占，何时少接纳比恢复更有效？
- [公平分配 Token 服务：加权计数与缓存局部性额度](balance-token-service-weighted-counters-and-locality-deficits_zh.md)：加权 token 服务与缓存局部性 deficit，如何区别于相同请求数？
- [按层组推进预填充，减少 MoE 专家权重流量](reduce-moe-weight-traffic-through-layered-prefill_zh.md)：何时沿层切分可以减少小 token 块重复读取专家权重？

引擎负责批次执行与缓存可执行性。[路由与准入](../routing-admission/README_zh.md)讨论入口等待、选实例和过载决策；这些控制不能独立保证引擎下一 token 的执行顺序。

返回[推理知识库](../README_zh.md)。
