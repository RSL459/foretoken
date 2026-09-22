<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router

Router 为每个推理请求选择兼容且健康的模型目标。

在 `FrontendService.spec.routerPipeline` 中配置路由策略：

```yaml
spec:
  routerPipeline:
    filter:
      algorithm: allow_all
    scorer:
      algorithm: kv_least_loaded
    picker:
      algorithm: round_robin
```

| 阶段 | 当前可选值 | 默认值 | 作用 |
| --- | --- | --- | --- |
| Filter | `allow_all` | `allow_all` | 保留全部兼容且健康的目标 |
| Scorer | `kv_least_loaded`、`least_loaded`、`uniform`、`queue_depth`、`running_request`、`kv_cache_utilization`、`active_request`、`token_load` | `kv_least_loaded` | 为保留目标评分 |
| Picker | `max`、`round_robin` | `round_robin` | 从最高分目标中选择一个 |

`kv_least_loaded` 优先选择可复用前缀更长的目标；长度相同时，依次比较已确认的设备、本机 CPU、本机磁盘和外部 Store，再比较负载。无法提供完整缓存身份的层级不会获得位置偏好。`least_loaded` 忽略 KV 位置，只按当前请求负载评分。`uniform` 为所有候选项赋予相同分数；`round_robin` 会在同分目标之间按确定顺序轮转，`max` 则选择一个确定的同分目标。

将 `scorer` 设为 `queue_depth`，可优先选择调度器中等待请求较少的目标；设为 `running_request`，可优先选择运行请求较少的目标；设为 `kv_cache_utilization`，可优先选择实测 KV cache 使用率较低的目标。

将 `scorer.algorithm` 设为 `active_request`，即可优先选择当前 frontend 跟踪的活跃请求较少的目标；如需调整默认行为，可配置 `scorer.parameters.idleThreshold` 和 `scorer.parameters.maxBusyScore`。

将 `scorer.algorithm` 设为 `token_load`，即可优先选择 frontend 本地在途 token 负载较低、且当前请求未缓存 prompt token 较少的目标；可通过 `scorer.parameters.queueThresholdTokens` 调整饱和阈值。

只有健康、支持所请求模型、输入限制和请求能力的目标才会参与路由。对于预填充/解码分离或编码/预填充/解码分离的服务，路由会保持选中阶段之间的兼容关系。

KV 索引不可用时，目标仍可参与路由，但不获得 KV 前缀匹配优先权。缓存位置行为见 [KV 前缀索引](../kv-indexer/README_zh.md)。
