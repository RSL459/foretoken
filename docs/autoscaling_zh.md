<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 模型服务自动扩缩容

[English](autoscaling.md) | [中文](autoscaling_zh.md)

在 `ModelService.spec.autoscaling` 中配置自动扩缩容。Controller 使用已编译的内置算法，用户不需要修改 CRD 或注册算法。

## 最小配置

将以下配置加入 `ModelService`：

```yaml
spec:
  replicas: 1
  autoscaling:
    minReplicas: 1
    maxReplicas: 8
    decision:
      algorithm: queue
```

该配置每 5 秒评估一次队列负载，每次最多调整一个副本。未填写时，触发阶段默认使用 `periodic`，调整阶段默认使用 `step`。

## 可选参数

每个阶段都使用 `algorithm` 和可选的 `parameters` 对象。省略参数时使用算法默认值。

| 阶段 | 算法 | 参数与默认值 |
| --- | --- | --- |
| Decision | `queue` | `targetAverageQueuedRequests: 1` |
| Decision | `queue_threshold` | `scaleUpQueuedRequests: 1`、`scaleDownQueuedRequests: 0` |
| Decision | `aimd` | `additiveIncrease: 1`、`multiplicativeDecreasePercent: 50`、`scaleUpQueuedRequests: 0` |
| Decision | `dynamo_load` | `mode: throughput`，可选 `latency` 或显式阈值的 `load` 模式 |
| Trigger | `periodic` | `interval: 5s` |
| Adjustment | `step` | `scaleUpStabilizationWindow: 0s`、`scaleDownStabilizationWindow: 300s` |
| Adjustment | `direct` | 不接受参数 |

例如，修改轮询间隔和缩容稳定窗口：

```yaml
trigger:
  algorithm: periodic
  parameters:
    interval: 10s
adjustment:
  algorithm: step
  parameters:
    scaleDownStabilizationWindow: 60s
```

未知算法或无效参数会使 `ModelService` 出现 `ScalingFailed` condition。

## Dynamo 反应式负载扩缩容

使用 `dynamo_load` 选择兼容 Dynamo 的反应式策略：

```yaml
decision:
  algorithm: dynamo_load
  parameters:
    mode: throughput
```

请配套使用从此分支构建的 controller 和 model-server 镜像。当前固定的 vLLM
版本支持单组全注意力 KV cache，且 PCP/DCP=1。旧引擎镜像、混合 cache 和
encoder Pool 不提供受支持的 token 负载观测，因此保持当前容量。

每个 DP rank 独立评估。Prefill 负载是排队 prompt token 数除以上下文长度；
decode 负载是已调度及排队 decode KV token 数之和除以 KV token 容量；
aggregate 额外计入排队 prompt token。这些信号表示工作需求，不是物理 KV cache 利用率。

| 模式 | Prefill 扩容 / 缩容 | Decode 和 aggregate 扩容 / 缩容 |
| --- | --- | --- |
| `throughput` | `>= 1` / `< 0.1` | `> 1` / `< 0.6` |
| `latency` | `>= 0.1` / `<= 0` | `> 0.4` / `< 0.1` |

任一 rank 超过扩容阈值即可建议扩容；所有 rank 满足缩容阈值后才考虑缩容。
缩容还检查重新分配后的需求仍低于扩容阈值。指标缺失、不完整或过期时保持容量。
已有稳定窗口、上下限、过渡状态约束和请求排空机制继续生效。
`latency` 使用反应式阈值，不包含 SLA 预测模型。

自定义阈值时选择 `mode: load`，并填写全部四个参数：

```yaml
decision:
  algorithm: dynamo_load
  parameters:
    mode: load
    prefillScaleUpQueueTokens: 8192
    prefillScaleDownQueueTokens: 0
    decodeScaleUpKVCacheUsage: 0.8
    decodeScaleDownKVCacheUsage: 0.6
```

此模式下 prefill 阈值是 token 数，decode 阈值是 `[0, 1]` 范围内的需求比例。
扩容阈值必须大于缩容阈值，扩缩容比较均包含等号。从此分支早期原型迁移时，
移除请求数参数，使用预设模式或上述四个显式阈值。
固定的 throughput/latency 预设模式不接受自定义阈值。

## 使用 AIMD

使用以下配置选择 AIMD：

```yaml
decision:
  algorithm: aimd
```

当队列超过 `scaleUpQueuedRequests` 时，AIMD 增加 `additiveIncrease` 个副本；没有等待请求和活跃请求时，保留当前容量的 `multiplicativeDecreasePercent`。最终容量仍受调整算法以及服务最小、最大副本数限制。

## 查看自动扩缩容结果

结果发布在 `.status.autoscaling[]` 中：

```bash
kubectl get modelservice <name> -o json \
  | jq '.status.autoscaling[] | {
      id,
      direction,
      desiredReplicas: .decision.desiredReplicas,
      adjustedReplicas: .adjustment.adjustedReplicas,
      appliedReplicas,
      constraint: .constraint.reason
    }'
```

`desiredReplicas` 是算法建议，`adjustedReplicas` 包含调整规则的结果，`appliedReplicas` 是应用服务约束后实际写入的容量。

完整的维护示例见[多模型示例](../examples/multi-model-quickstart/README_zh.md)，实现边界见[自动扩缩容架构指南](../control-plane/internal/autoscaling/README_zh.md)。
