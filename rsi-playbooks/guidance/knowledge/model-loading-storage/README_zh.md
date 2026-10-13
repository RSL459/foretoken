<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 模型加载与存储

[English](README.md) | 简体中文

- 模型早已下载，为什么启动仍然慢？[权重加载流水与 rank 本地检查点](weight-loading-pipeline_zh.md)区分 I/O、张量安装、转换与首请求就绪。
- 何时采用 lazy mmap、eager 读取、固定页缓冲区或并行 I/O？[Mmap、固定页内存与并行 I/O](mmap-pinned-parallel-io_zh.md)解释缺页、暂存寿命与有界流水容量。
- 热 worker 或共享存储能否加速其他 worker 加载？[分布式权重存储与 peer 加载](distributed-weight-storage_zh.md)核对 ModelExpress、Mooncake、Dynamo 的当前路径和兼容边界。
- 睡眠、重启与冷恢复分别保留什么？[冷热状态与 sleep/wake 恢复](sleep-wake-recovery_zh.md)区分主机备份、IPC 所有权、原始分配产物与 token 重放。

这里关注加载和存储机制。副本放置、缩容到零与请求路由属于服务编排，allocator 和 graph 内部机制属于运行时知识。

## 来源快照

核对日期为 2026-10-14。

- [LMCache、Mooncake、vLLM 与 Dynamo 版本](../kv-cache/README_zh.md#来源快照)：加载、存储与恢复的实现来源。
- [ModelExpress `main`](https://github.com/ai-dynamo/modelexpress/tree/db0cbce97184d9135d35c7290711f3053b220b6a)，提交于 UTC 2026-10-13：已接入上游的 vLLM loader 与加载策略链。

[推理知识](../README_zh.md) · [KV 缓存](../kv-cache/README_zh.md)
