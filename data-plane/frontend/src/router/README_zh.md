<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router

Router 为每个执行阶段选择一个可路由的 ModelGroup 和精确 DP rank。

Filter–Scorer–Picker 是候选列表级接口：

- **Filter** 接收兼容且健康的候选快照，返回保留子集的索引。它不能新增或修改候选；越界或重复索引会成为明确的路由错误。
- **Scorer** 按保留候选的原有顺序为每项返回一个 `RouteScore`。Router 持有 candidate/score 视图；数量不匹配会成为明确的路由错误。内置 KV 评分比较 prompt 命中长度、存储层级、locality 和负载。
- **Picker** 从当前评分列表选择一个索引，而不是回传候选。非空列表返回 `None` 或越界索引都会成为明确的路由错误。Router 随后输出 `RouteDecision`，其中包含 ModelGroup RouteTarget、执行角色、模型 revision 和精确 DP rank。

执行阶段和 E/P/D domain 收窄仍由 Router 负责，在评分后、Picker 前执行。算法可比较完整的兼容健康快照，但不能选择当前阶段收窄范围以外的候选。

`data_parallel_size: 1` 的 RouteTarget 只产生 rank `0` 候选，最终决策仍显式返回 `data_parallel_rank: 0`。更大的 RouteTarget 会为每个 rank 产生一个候选。

## 示例

```text
ModelGroups：
  llama3-serve-r-2gosa7pa2jpf2-0  UID 2f48f8e1-7f89-4eb8-bf31-e6d482504f66
  llama3-serve-r-2gosa7pa2jpf2-1  UID 8c88ee9a-c10f-41fd-98ef-a09d256b5213

候选：
  2f48f8e1-7f89-4eb8-bf31-e6d482504f66 / rank 0  KV 命中：  0 tokens
  2f48f8e1-7f89-4eb8-bf31-e6d482504f66 / rank 1  KV 命中：512 tokens
  8c88ee9a-c10f-41fd-98ef-a09d256b5213 / rank 0  KV 命中：256 tokens

Filter：保留索引 0、1、2
Scorer：索引 0 → 0，1 → 512，2 → 256
Picker：选择索引 1

RouteDecision：
  route_target_id: 2f48f8e1-7f89-4eb8-bf31-e6d482504f66
  data_parallel_rank: 1
```

ModelGroup 名称遵循 `<pool-name>-<revision>-<ordinal>`。Router 使用 Kubernetes ModelGroup UID 作为路由身份，而不是使用 `metadata.name`；Deployment、Service 和 Service DNS endpoint 使用 ModelGroup 名称。

Aggregate 和 Prefill 的内置 KV 评分按以下顺序做字典序比较：完整 prompt prefix 命中长度、`Device > HostPinned > Disk > External`、`Local > Remote`，最后比较负载。Decode 的 prefix、tier 和 locality 分数为零。Unavailable KV facts 不会被当作确认 miss。
