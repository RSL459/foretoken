<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 模型服务自动扩缩容

[English](autoscaling.md) | [中文](autoscaling_zh.md)

根据请求队列负载调整模型副本数。在 `examples/quickstart/model.yaml` 已有的 `spec` 下加入 `autoscaling`：

```yaml
spec:
  replicas: 1
  autoscaling:
    minReplicas: 1
    maxReplicas: 3
    decision:
      algorithm: queue
```

服务从 1 个副本开始，每 5 秒评估一次负载。默认每次最多增减 1 个副本，缩容稳定窗口为 5 分钟。快速开始每增加一个模型副本，需要 1 张 GPU、4 核 CPU 和 48 GiB 内存。

```bash
foretoken deploy examples/quickstart --timeout 20m
```

需要直接运行产生队列压力的负载时，使用[多模型示例](../examples/multi-model-quickstart/README_zh.md)。

## 查看容量

```bash
kubectl get modelservice quickstart-qwen3-0.6b -n foretoken-demo -o json \
  | jq '.status.autoscaling[] | {
      direction,
      desiredReplicas: .decision.desiredReplicas,
      appliedReplicas,
      constraint: .constraint.reason
    }'
```

`desiredReplicas` 是算法建议，`appliedReplicas` 是经过稳定窗口和服务约束后选定的容量。无效算法或参数会显示为 ModelService 的 `ScalingFailed` condition。

## 调整对流量的响应

默认 `queue` 算法的目标是每个副本对应 1 个等待请求。`queue_threshold` 按显式队列阈值扩缩容，`aimd` 则采用加法扩容、乘法缩容。

队列超过 `scaleUpQueuedRequests` 时，AIMD 增加 `additiveIncrease` 个副本；没有等待或活跃请求时，保留当前容量的 `multiplicativeDecreasePercent`。最终容量仍受调整设置和最小、最大副本数限制。

如需修改评估间隔或稳定窗口，在 `spec.autoscaling` 的 `decision` 同级添加：

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

`step` 将每次容量变化限制为 1 个副本；`direct` 不做步长调整，直接应用建议。两者都遵守服务的最小、最大副本数。未填写参数时使用以下默认值：

| 设置 | 算法 | 参数与默认值 |
| --- | --- | --- |
| 副本建议 | `queue` | `targetAverageQueuedRequests: 1` |
| 副本建议 | `queue_threshold` | `scaleUpQueuedRequests: 1`、`scaleDownQueuedRequests: 0` |
| 副本建议 | `aimd` | `additiveIncrease: 1`、`multiplicativeDecreasePercent: 50`、`scaleUpQueuedRequests: 0` |
| 评估间隔 | `periodic` | `interval: 5s` |
| 容量调整 | `step` | `scaleUpStabilizationWindow: 0s`、`scaleDownStabilizationWindow: 300s` |
| 容量调整 | `direct` | 无参数 |
