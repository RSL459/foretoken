<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 并行与通信

[English](README.md) | 简体中文

先追踪阻止下一步有效计算的依赖，不只看最长通信核函数。

- MoE dispatch/combine 主导小批 decode？[通过微批与块级计算重叠隐藏 MoE 通信](hide-moe-communication-through-microbatch-and-block-overlap_zh.md)解释 DeepEP V2.5、vLLM DBO、分支特定 SBO，以及独立工作不足时的 SM 争用。
- 增加 TP 后同步成本增长超过计算缩短？[按消息形状选择 Collective，减少张量并行同步开销](reduce-tp-synchronization-through-shape-aware-collective-selection_zh.md)追踪 all-reduce/AG/RS 的张量归属、eager 与图注册缓冲区，以及 MNNVL 特定选择。
- 长上下文计算或 KV 历史切分不正确、不高效？[通过 Query 与 KV 分片扩展长上下文注意力](scale-context-attention-through-query-and-kv-sharding_zh.md)区分 Ulysses/ring prefill、因果负载平衡、paged-history DCP 和局部输出归一化合并。
- 跨节点 PP 容纳了模型，却留下空闲阶段？[通过微批调度平衡流水线并行的延迟与吞吐](balance-pipeline-latency-and-throughput-through-microbatching_zh.md)区分单请求串行延迟、流水线占用、阶段平衡和已有传输原语。
- 专家计算均衡，慢链路却拥塞？[通过拓扑感知的专家副本放置平衡计算与链路负载](balance-expert-network-load-through-topology-aware-replica-placement_zh.md)连接逻辑路由组、节点内副本、副本图和迁移流量。

本地专家核函数、小批调度、量化表示与两种均衡时间尺度见 [MoE 执行](../moe-execution/README_zh.md)。使用[部署配方](../../../../examples/recipes/README_zh.md)在真实 rank/GPU/NIC 拓扑上运行[性能评测](../../../../benchmarks/docs/perf/README_zh.md)，[剖析捕获](../../../../benchmarks/docs/profile/README_zh.md)与测速分开，并通过[质量评测](../../../../benchmarks/docs/eval/README_zh.md)完成模型行为对照。

返回[推理知识库](../README_zh.md)。
