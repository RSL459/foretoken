<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router

## Router 解决什么问题

同一个模型可以由多个 ModelGroup 提供服务，每个 ModelGroup 还可能包含多个 DP rank。Router 为一次请求选择具体的路由目标和 DP rank，并返回 `RouteDecision`。

Router 不执行模型推理。它只根据当前可用的路由目标、请求要求、KV cache 命中和负载等信息完成选择。

## 一次请求如何完成路由

```text
RouterRequest
    ↓
兼容且健康的候选路由项
    ↓ Filter
保留的候选路由项
    ↓ Scorer
带分数的候选路由项
    ↓ Picker
RouteDecision
```

### 候选路由项

Router 从 `RouteInventory` 获取路由目标。只有模型、revision、输入限制和请求能力兼容且当前健康的目标才会成为候选项。执行角色会保留在候选项中，供后续执行阶段筛选。

一个 `RouteTarget` 会按 `data_parallel_size` 展开为候选项：

- `data_parallel_size: 1` 产生 rank `0`；
- 更大的值为每个 DP rank 产生一个候选项。

候选项还包含 Router 在本轮读取的负载和运行状态。算法使用这份快照，不需要自行查询模型服务器。

### Filter、Scorer 和 Picker

路由流程由三个可替换的接口组成：

- **Filter** 返回要保留的候选项索引，用于排除不满足策略要求的候选项。
- **Scorer** 按原顺序为每个保留候选项返回一个 `RouteScore`。
- **Picker** 从当前评分列表中选择一个索引。

三个接口都使用索引，而不是创建或返回新的候选项。候选项始终由 Router 持有，因此算法不能修改路由身份或选择列表之外的目标。重复索引、越界索引和分数数量不匹配都会成为明确的路由错误。

## 一个完整示例

假设有两个健康的 ModelGroup：

```text
候选项：
  ModelGroup A / rank 0  KV 命中 0 tokens
  ModelGroup A / rank 1  KV 命中 512 tokens
  ModelGroup B / rank 0  KV 命中 256 tokens

Filter：保留索引 0、1、2
Scorer：为三个候选项分别生成分数
Picker：选择索引 1

RouteDecision：
  route_target_id: ModelGroup A
  data_parallel_rank: 1
```

`route_target_id` 是 Model Server Registry 提供的稳定路由身份。`RouteDecision` 还会返回执行角色、模型、revision 和精确 DP rank。

## 使用 KV 前缀信息

Filter 和 Scorer 都会接收 `&dyn KvPrefixIndexer`。KV 感知算法使用候选项的路由目标和 DP rank 查询可复用的 prompt 前缀：

```rust
use foretoken_kv_indexer::KvPrefixQueryResult;

let result = request
    .kv_prefix_lookup(
        candidate.route_target_id.as_str(),
        candidate.data_parallel_rank,
    )
    .map_or_else(KvPrefixQueryResult::Unavailable, |lookup| {
        kv_prefix_indexer.prefix_matches(lookup)
    });

let matched_tokens = match result {
    KvPrefixQueryResult::Matches(matches) => matches
        .into_iter()
        .map(|matched| matched.matched_tokens)
        .max()
        .unwrap_or(0),
    KvPrefixQueryResult::Unavailable(_) => 0,
};
```

`Unavailable` 表示当前无法可靠查询，不是已经确认的 cache miss，不能仅凭它删除候选项。KV 前缀索引的职责和扩展方式见 [`../kv-indexer/README_zh.md`](../kv-indexer/README_zh.md)。

## 添加自定义算法

### 实现算法接口

根据需要实现 `RouteFilter`、`RouteScorer` 或 `RoutePicker`。实现应只使用 Router 提供的请求、候选项和观测快照，不应修改候选项或在算法内部维护另一份路由目录。

社区算法放在对应目录：

```text
src/algorithm/filter/
src/algorithm/scorer/
src/algorithm/picker/
```

### 注册算法

算法通过 `inventory::submit!` 在编译期注册稳定名称和 factory，并在对应目录的 `mod.rs` 中声明模块：

```rust
mod my_algorithm;
```

不需要修改中央算法清单，也不依赖源码扫描、runtime plugin loader、`build.rs` 或 codegen。Router 启动时会校验配置引用的算法名称；空名称、重复名称和未知名称都会返回明确错误。

## 请求级 Context

多数算法不需要额外状态，可以使用 `RouterPipeline::new`。如果 Filter、Scorer 和 Picker 需要在同一个请求内共享状态，可使用 `RouterPipeline::with_customized_context`：

```rust
let pipeline = RouterPipeline::with_customized_context(
    Arc::new(ContextFilter),
    Arc::new(ContextScorer),
    Arc::new(ContextPicker),
    |_| RoutingContext { rounds: 0 },
);
```

Router 为每个请求创建独立的 Context，并在该请求的每轮选择中依次传给 Filter、Scorer 和 Picker。请求结束后 Context 被释放，不会与其他请求共享。

## E/P/D 多阶段路由

一个请求可能由关联的 Encoder、Prefill 和 Decode 路由组件共同完成。Router 会为每个需要的执行阶段分别选择目标，并确保这些目标属于同一个 pipeline scope。

算法可以为完整的兼容健康候选快照评分。Router 在评分后、Picker 前根据当前执行阶段和已选择的 pipeline scope 收窄候选范围，因此 Picker 不能选择关联组件集之外的目标。同一个请求级 Context 会贯穿这些选择阶段。
