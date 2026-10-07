<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Autoscale Model Services

[English](autoscaling.md) | [中文](autoscaling_zh.md)

Scale model replicas with request queue demand. Add `autoscaling` under the existing `spec` in `examples/quickstart/model.yaml`:

```yaml
spec:
  replicas: 1
  autoscaling:
    minReplicas: 1
    maxReplicas: 3
    decision:
      algorithm: queue
```

This starts with one replica and evaluates demand every five seconds. By default, capacity changes by at most one replica per evaluation, with a five-minute scale-down stabilization window. Each additional Quick Start replica needs one GPU, 4 CPU cores, and 48 GiB of memory.

```bash
foretoken deploy examples/quickstart --timeout 20m
```

For a ready-to-run workload that generates queue pressure, use the [multi-model example](../examples/multi-model-quickstart/README.md).

## Inspect capacity

```bash
kubectl get modelservice quickstart-qwen3-0.6b -n foretoken-demo -o json \
  | jq '.status.autoscaling[] | {
      direction,
      desiredReplicas: .decision.desiredReplicas,
      appliedReplicas,
      constraint: .constraint.reason
    }'
```

`desiredReplicas` is the recommendation; `appliedReplicas` is the capacity selected after stabilization and service constraints. Invalid algorithms or parameters appear as a `ScalingFailed` condition on the ModelService.

## Tune the response to traffic

The default `queue` algorithm targets one waiting request per replica. Use `queue_threshold` for explicit scale-up and scale-down queue thresholds, or `aimd` for additive increases and multiplicative decreases.

AIMD adds `additiveIncrease` replicas when the queue exceeds `scaleUpQueuedRequests`. With no waiting or active requests, it retains `multiplicativeDecreasePercent` of capacity. The adjustment settings and min/max limits still apply.

To change the polling interval or stabilization window, add `trigger` and `adjustment` beside `decision` under `spec.autoscaling`:

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

`step` limits each evaluation to a one-replica change; `direct` applies the recommendation without step adjustment. Both respect the service's min/max limits. Omitted parameters use these defaults:

| Setting | Algorithm | Parameters and defaults |
| --- | --- | --- |
| Replica recommendation | `queue` | `targetAverageQueuedRequests: 1` |
| Replica recommendation | `queue_threshold` | `scaleUpQueuedRequests: 1`, `scaleDownQueuedRequests: 0` |
| Replica recommendation | `aimd` | `additiveIncrease: 1`, `multiplicativeDecreasePercent: 50`, `scaleUpQueuedRequests: 0` |
| Evaluation interval | `periodic` | `interval: 5s` |
| Capacity adjustment | `step` | `scaleUpStabilizationWindow: 0s`, `scaleDownStabilizationWindow: 300s` |
| Capacity adjustment | `direct` | No parameters |
