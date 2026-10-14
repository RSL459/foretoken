<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 模型加载与存储

[English](README.md) | 简体中文

- 模型早已下载，为什么启动仍然慢？[通过 Rank 本地检查点与加载流水降低启动成本](reduce-startup-cost-through-sharded-checkpoints-and-pipelining_zh.md)区分 I/O、张量安装、转换与首请求就绪。
- 何时采用 lazy mmap、eager 读取、固定页缓冲区或并行 I/O？[平衡加载速度与内存：Mmap、固定页暂存和并行 I/O](balance-loading-speed-memory-mmap-pinned-staging-parallel-io_zh.md)解释缺页、暂存寿命与有界流水容量。
- 热 worker 或共享存储能否加速其他 worker 加载？[通过 Peer 与共享存储复用降低权重加载成本](reduce-weight-loading-cost-peer-and-shared-storage_zh.md)说明 ModelExpress、Mooncake、Dynamo 的当前路径和兼容边界。
- 睡眠、重启与冷恢复分别保留什么？[降低恢复延迟：休眠唤醒与保留状态复用](reduce-recovery-latency-sleep-wake-and-state-reuse_zh.md)区分主机备份、IPC 所有权、原始分配产物与 token 重放。

这里关注加载和存储机制。副本放置、缩容到零与请求路由属于服务编排，allocator 和 graph 内部机制属于运行时知识。

## 参考

- [LMCache、Mooncake、vLLM 与 Dynamo 版本](../kv-cache/README_zh.md#参考)：加载、存储与恢复的实现来源。
- [ModelExpress `main`](https://github.com/ai-dynamo/modelexpress/tree/db0cbce97184d9135d35c7290711f3053b220b6a)，提交于 UTC 2026-10-13：已接入上游的 vLLM loader 与加载策略链。

[推理知识](../README_zh.md) · [KV 缓存](../kv-cache/README_zh.md)
