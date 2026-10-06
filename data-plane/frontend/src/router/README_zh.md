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

## 配置准入规则

准入规则决定请求直接执行、等待还是被拒绝。默认使用 `allow_all`，不限制请求；选择 `concurrency` 可启用并发流控：

```yaml
spec:
  routerPipeline:
    admission:
      algorithm: concurrency
      parameters:
        maxConcurrentRequests: 64
```

示例允许每个前端副本同时执行 64 个输出候选，具体数值应根据负载实测选择。批量补全按候选计数，例如四个 prompt、`n: 2` 占用八个名额。

需要吸收短时突发流量时，可在 `parameters` 下增加 `maxQueuedRequests: 128` 和 `queueTimeout: 2s`。默认不排队；允许排队但未设置等待时限时，使用请求剩余的超时预算。容量和等待队列均已满，或排队超时，返回 HTTP 503；单个批次超过并发上限时返回 HTTP 400。

每个前端副本上的模型共用这些限制，不是集群总配额。规则适用于文本生成和 tokenization，不包括视频请求；健康探针不受影响。

开发自定义规则请参阅[准入规则开发指南](../../../../docs/development/admission-rules_zh.md)。
