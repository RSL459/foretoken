<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Predictive Scaling and Cold Start

English | [简体中文](predictive-scaling-and-cold-start_zh.md)

## Problem and mechanism

A replica requested now may become useful minutes later. Scrape, smoothing, decision, scheduling, image loading, checkpoint loading, graph warmup and route publication all contribute to that delay. A sophisticated one-step forecast can still be structurally late if it predicts only the next 15-second sample while startup takes 180 seconds.

Predict demand at the time capacity becomes ready. A simple illustrative controller smooths token demand `x̂_t = α*x_t + (1−α)*x̂_(t−1)` and extrapolates its trend over measured startup Δ. Add a bounded uncertainty margin, then divide projected prefill/decode work by calibrated capacity. The 2026 decomposition paper uses `x̂_(t+Δ) = x̂_t + slope*(Δ−T/2)` for interval T and `margin = β*min(σ, γ*abs(x̂_(t+Δ)))`.

Track requested, starting, ready, routable and draining replicas separately. Two ready replicas plus two starting ones are neither two nor four units of current serving capacity. The starting units should reduce duplicate scale-up requests without being credited as immediate throughput. Failed or unschedulable starts need different treatment from starts whose normal warmup is still progressing.

For an arithmetic example, demand rises from 10 to 20 requests/s over 60 seconds, each replica serves 5, and startup is 120 seconds. A reactive controller reaches a target of four only after observing pressure; those replicas arrive after the ramp. Predictive provisioning can act earlier only if the rise is observable or scheduled. No forecast predicts a completely unannounced jump; a warm floor or admission policy handles that uncertainty at a real cost.

## Hardware and published evidence

[Decomposing Predictive Kubernetes Autoscaling](https://arxiv.org/html/2609.20874v1) separates token tracking, lookahead, uncertainty and plant-state observation. Its simulation uses five seeds and a 180-second startup; absolute simulated TTFT is about twice the calibrated hardware value, so relative comparisons are the stronger evidence.

The physical validation uses Qwen2.5-7B-Instruct, vLLM 0.11, A100 40GB, one GPU per replica, and an injected 60-second startup sleep. It reports reduced TTFT violations for delay-aware EWMA compared with reactive KEDA. Dtype is not specified, the hardware study is small, and it does not validate P/D behavior. The article promises artifacts upon publication rather than providing a code URL. These boundaries matter when reusing its controller design.

Checkpoint storage, quantization, CPU deserialization and graph sizes change startup independently of steady-state throughput. FP8 can reduce weight bytes while adding conversion or kernel preparation. Measure cold and cache-warm starts separately; a deliberately injected sleep isolates delay but does not reproduce every real loading bottleneck.

## Current public implementations

Checked 2026-10-14. Dynamo's [predictors](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/load/predictors.py) already include constant, ARIMA, Prophet and Kalman options; their `predict_next` interfaces are one-step predictors. Its [throughput scaler](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py) includes pending-start and performance-model-readiness handling. Predictor availability alone does not prove a startup-distribution-aware forecast.

AIBrix's [predictive documentation](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/docs/source/features/scaling-performance/autoscaling/predictive-autoscaling.rst) explicitly says the fields are accepted/validated but controller consumption is deferred. Its [autoscaler code](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/controller/podautoscaler/autoscaler.go) shows reactive collection/aggregation/recommendation and pending-replica handling, not implemented predictive actuation. Do not mistake the proposed Preview/Auto semantics for delivered behavior.

Foretoken's [autoscaling architecture](../../../../control-plane/internal/autoscaling/README.md) holds transitioning targets and keeps stabilization history in the current controller process. Its [public policies](../../../../docs/autoscaling.md) do not establish forecasting. Load-state preparation belongs to the controller; a predictor should return recommendations through the existing algorithm boundary.

## Experiments and remaining questions

Use a trace-driven delayed-actuation simulation to compare reactive, token-only, lookahead-only and lookahead-plus-margin policies. Sweep startup distributions, abrupt jumps, trend reversals, metric delay and unavailable GPUs. Score SLO violations against GPU-seconds, not prediction error alone.

Then run real cold/warm starts under the same arrival trace. Record each lifecycle timestamp, pending credit, actual startup quantiles, routing visibility and transient failures. Compare simple EWMA with complex forecasting at equal resource cost. Remaining questions include delay-distribution calibration, cancellation of obsolete starts and cross-model competition for the same GPU budget. Loading mechanisms are in [model loading and storage](../model-loading-storage/README.md).

[Back to autoscaling and placement](README.md)
