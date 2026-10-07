<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# KV 前缀索引

[English](README.md) | 中文

KV 前缀索引帮助路由复用模型副本已缓存的输入 token。本地加速器缓存表示为 `Device/Local`，文件缓存表示为 `Disk/Local`，Mooncake 共享内存或 SSD 缓存表示为 `External/Remote`。前缀查询支持未使用 LoRA 且允许读取前缀缓存的文本请求。

直接使用缓存感知路由时，按[路由指南](../router/README_zh.md)选择评分算法即可。

## 在算法中使用前缀匹配

在 `RouteFilter` 或 `RouteScorer` 中实现以下方法，声明需要前缀观测：

```rust
fn needs_kv_prefix(&self) -> bool {
    true
}
```

在 `filter` 或 `score` 中使用传入的查询器，按候选目标和准确的数据并行 rank 查询。路由在调用算法前准备外部观测，算法中的查询是同步的：

```rust
use foretoken_kv_indexer::{KvPrefixIndexer, KvPrefixQueryResult};
use foretoken_router::{RouteCandidate, RouterRequest};

fn candidate_prefix(
    request: &RouterRequest,
    candidate: &RouteCandidate,
    indexer: &dyn KvPrefixIndexer,
) -> KvPrefixQueryResult {
    match request.kv_prefix_lookup(
        &candidate.route_target_id,
        candidate.data_parallel_rank,
    ) {
        Ok(lookup) => indexer.prefix_matches(lookup),
        Err(reason) => KvPrefixQueryResult::Unavailable(reason),
    }
}
```

每项匹配包含缓存位置 `placement` 和匹配长度 `matched_tokens`。空的 `Matches` 表示未命中，`Unavailable` 表示无法判断；无法判断的候选仍可参与常规路由。

## 查看索引健康状态

通过前端的 `/statusz` 查看索引健康状态，通过 `/metrics` 监控。访问方式见[前端运维](../../README_zh.md#运维)。
