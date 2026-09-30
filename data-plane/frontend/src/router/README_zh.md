<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router

Router 根据请求的模型、输入长度和能力要求，选择兼容且健康的目标；对于预填充/解码分离及编码/预填充/解码分离的服务，还会确保各阶段相互兼容。

例如，要优先选择等待请求较少的目标，可在 `FrontendService` 中配置：

```yaml
spec:
  routerPipeline:
    scorer:
      algorithm: queue_depth
```

只有需要调整路由策略时才填写 `spec.routerPipeline`。默认保留全部兼容目标（`allow_all`），用 `kv_least_loaded` 评分，再由 `gamble_sampling` 选取目标。各阶段通过 `algorithm` 选择算法；评分算法的可调选项写在 `scorer.parameters` 下。

| 阶段 | 算法 | 选择方式 |
| --- | --- | --- |
| Filter | `allow_all`（默认） | 保留所有兼容且健康的目标。 |
| Scorer | `kv_least_loaded`（默认） | 优先考虑可复用的 KV 前缀、已确认的缓存位置，再比较当前及下游 Decode 负载。 |
| Scorer | `least_loaded` · `uniform` | 优先选择低负载目标 · 为所有目标赋予相同分数。 |
| Scorer | `queue_depth` · `running_request` · `kv_cache_utilization` | 分别优先选择等待请求少、运行请求少或实测 KV 缓存占用低的目标。 |
| Scorer | `active_request` | 优先选择当前前端活跃请求较少的目标；可用 `idleThreshold`、`maxBusyScore` 调整。 |
| Scorer | `token_load` | 优先选择在途 token 和当前请求未缓存 prompt token 负载较低的目标；可用 `queueThresholdTokens` 调整。 |
| Scorer | `prefix` | 优先考虑可复用的 prompt 缓存块；可用 `matchLengthWeight`、`matchLengthScaleTokens` 调整匹配长度偏好。 |
| Scorer | `no_hit_lru` | 优先选择尚未处理过冷请求的端点，其次选择最久未选中的端点；最多保留 `lruSize` 条记录。 |
| Scorer | `load_aware` | 空等待队列记为 0.5 分，并随队列长度线性下降，在 `threshold` 处降至零。 |
| Scorer | `session_affinity` | 优先选择请求体 `session_id` 绑定的目标及 rank；可用 `sessionIdConfig.evictionTtlSeconds`、`sessionIdConfig.evictionSweepSeconds` 调整闲置清理。 |
| Picker | `gamble_sampling`（默认） | 根据完整分数排名采样：排名越高，选中概率越大；同分概率相同，低排名目标仍有机会被选中。 |
| Picker | `max` · `power_of_two_choices` | 选择最高分目标 · 随机抽取两个不同目标，选择分数较高者，同分时随机选取。 |

KV 索引不可用时，目标仍可参与路由，只是不享有 KV 前缀偏好。缓存位置的说明见 [KV 前缀索引](../kv-indexer/README_zh.md)。

`session_affinity` 仅支持 `strategy: session_id`，它也是默认值。在同一会话的 Chat Completions、Completions 或 Responses 请求体中携带相同的非空 `session_id`，标识首尾空白会被去除。可用的绑定目标记为 1 分，其他候选记为 0 分；标识缺失、新会话或原目标不可选时全部记为 0 分。搭配 `max` picker 可遵循可用绑定；采样选中其他目标不会修改绑定或刷新计时。绑定在选中目标后提交，原目标不再可选时才会迁移。

绑定由各前端流水线按路由阶段分别持有，服务快照更新时保留，不同副本间不共享。`scorer.parameters.sessionIdConfig` 下的闲置 TTL 默认取 300 秒，清理间隔默认取 10 秒；零值使用默认值，负值会被拒绝。选中原绑定目标会刷新计时。定时清理只移除闲置时间严格超过 TTL 的绑定；清理前仍可使用并刷新。替换流水线或重启前端会清空绑定。
