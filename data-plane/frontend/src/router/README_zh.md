<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router

Router 根据请求的模型、输入长度和能力要求，选择兼容且健康的目标；对于预填充/解码分离及编码/预填充/解码分离的服务，还会确保各阶段相互兼容。

## 选择路由策略

例如，要优先选择等待请求较少的目标，可在 `FrontendService` 中配置：

```yaml
spec:
  routerPipeline:
    scorer:
      algorithm: queue_depth
```

不填写 `filter`、`scorer` 和 `picker` 时使用默认策略：保留全部兼容目标（`allow_all`），用 `kv_least_loaded` 评分，再由 `gamble_sampling` 选取目标。各阶段通过 `algorithm` 选择算法；评分算法的可调选项写在 `scorer.parameters` 下。

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
| Scorer | `two_tier` | 负载差异同时超过两个阈值时优先选择活跃请求少的目标；否则优先选择超过 `cache_threshold` 的最大 Device 前缀重叠量。必须搭配 `max` picker。 |
| Picker | `gamble_sampling`（默认） | 根据完整分数排名采样：排名越高，选中概率越大；同分概率相同，低排名目标仍有机会被选中。 |
| Picker | `max` · `power_of_two_choices` | 选择最高分目标 · 随机抽取两个不同目标，选择分数较高者，同分时随机选取。 |

KV 索引不可用时，目标仍可参与路由，只是不享有 KV 前缀偏好。缓存位置的说明见 [KV 前缀索引](../kv-indexer/README_zh.md)。

## 限制并发请求

在 `FrontendService` 中增加 Admission 阶段，可以限制每个前端副本同时接受的生成任务：

```yaml
spec:
  routerPipeline:
    admission:
      parameters:
        maxConcurrentRequests: 64
```

示例允许同时执行 64 个生成任务，容量用尽时以 HTTP 503 拒绝新请求。64 只是示例值，应根据实际负载测量选择；省略 `admission` 时不启用此保护。算法默认为 `concurrency`，无需额外填写。

希望吸收短时突发流量时，可在同一个 `parameters` 下增加 `maxQueuedRequests: 128` 和 `queueTimeout: 2s`。已入队的请求按先入先出顺序获得容量，之后才进行预处理和选路。

| 参数 | 用途 | 缺省行为 |
| --- | --- | --- |
| `maxConcurrentRequests` | 每个前端副本的最大并发生成数 | 必填 |
| `maxQueuedRequests` | 最多允许多少个生成任务等待容量 | `0`，不排队 |
| `queueTimeout` | 最长准入等待时间 | 使用请求剩余的超时预算 |

批量补全按每个输出候选计数，例如四个 prompt、`n: 2` 需要八个名额。单个批次超过并发上限时返回 HTTP 400；容量或等待队列已满、排队超时则返回 HTTP 503，请求总超时仍然生效。文本生成和 tokenization 接口共用此保护，视频请求和后台视频任务不在其范围内。

这些限制由每个前端副本上的各模型共用，不是集群总配额。容量满时健康探针仍然可用，Admission 不改变 Filter、Scorer 和 Picker 的选路策略。
