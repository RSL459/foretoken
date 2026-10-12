<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Autoscale Model Services

[English](autoscaling.md) | [中文](autoscaling_zh.md)

Configure autoscaling in `ModelService.spec.autoscaling`. The controller uses the selected built-in algorithms; users do not edit CRDs or register algorithms.

## Minimal configuration

Add this block to a `ModelService`:

```yaml
spec:
  replicas: 1
  autoscaling:
    minReplicas: 1
    maxReplicas: 8
    decision:
      algorithm: queue
```

This evaluates queue demand every five seconds and changes at most one replica per evaluation. `periodic` triggering and `step` adjustment are the defaults, so they can be omitted.

## Optional parameters

Every stage accepts an `algorithm` and an optional `parameters` object. Omitted parameters use the algorithm defaults.

| Stage | Algorithm | Parameters and defaults |
| --- | --- | --- |
| Decision | `queue` | `targetAverageQueuedRequests: 1` |
| Decision | `queue_threshold` | `scaleUpQueuedRequests: 1`, `scaleDownQueuedRequests: 0` |
| Decision | `aimd` | `additiveIncrease: 1`, `multiplicativeDecreasePercent: 50`, `scaleUpQueuedRequests: 0` |
| Decision | `dynamo_load` | `mode: throughput` (`latency` or explicit `load` thresholds optional) |
| Trigger | `periodic` | `interval: 5s` |
| Adjustment | `step` | `scaleUpStabilizationWindow: 0s`, `scaleDownStabilizationWindow: 300s` |
| Adjustment | `direct` | No parameters |

For example, change the polling interval and scale-down window:

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

Unknown algorithms and invalid parameters produce a `ScalingFailed` condition on the `ModelService`.

## Dynamo reactive load

Select `dynamo_load` for a Dynamo-compatible reactive policy:

```yaml
decision:
  algorithm: dynamo_load
  parameters:
    mode: throughput
```

Use a controller and model-server image built from this branch together. The
current pinned vLLM runtime supports this policy for single-group full-attention
KV caches with PCP/DCP=1. Older engine images, hybrid caches, and encoder Pools
have no supported token-load observation and keep their current capacity.

Each DP rank is evaluated separately. Prefill demand is queued prompt tokens
normalized by context length; decode demand is scheduled plus queued decode KV
tokens divided by KV token capacity. Aggregate demand also includes queued prompt
tokens. These are demand signals, not physical KV cache utilization.

| Mode | Prefill up / down | Decode and aggregate up / down |
| --- | --- | --- |
| `throughput` | `>= 1` / `< 0.1` | `> 1` / `< 0.6` |
| `latency` | `>= 0.1` / `<= 0` | `> 0.4` / `< 0.1` |

One overloaded rank can request expansion; all ranks must meet the down threshold
before contraction. Contraction also checks that redistributed demand stays below
the up threshold. Missing, incomplete, or stale observations hold capacity.
Existing stabilization, min/max bounds, transition handling, and draining apply.
`latency` uses reactive thresholds; it does not implement an SLA prediction model.

For explicit thresholds, choose `mode: load` and supply all four parameters:

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

Prefill thresholds in this mode are token counts; decode thresholds are demand
ratios in `[0, 1]`. The up threshold must exceed the down threshold. Up/down
comparisons are inclusive. To migrate the earlier branch prototype, remove
request-count parameters and use a preset or the four explicit thresholds above.
Custom thresholds are not accepted with the fixed throughput/latency presets.

## AIMD

Select AIMD with:

```yaml
decision:
  algorithm: aimd
```

AIMD adds `additiveIncrease` replicas when the queue exceeds `scaleUpQueuedRequests`. When there are no waiting or active requests, it keeps `multiplicativeDecreasePercent` of the current capacity. The selected adjustment algorithm and service min/max limits still apply.

## Observe autoscaling

Autoscaling results are published in `.status.autoscaling[]`:

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

`desiredReplicas` is the algorithm recommendation. `adjustedReplicas` includes adjustment rules, and `appliedReplicas` is the capacity written after service constraints.

For the complete maintained workload, see the [multi-model example](../examples/multi-model-quickstart/README.md). The implementation boundary is documented in the [Autoscaling architecture guide](../control-plane/internal/autoscaling/README.md).
