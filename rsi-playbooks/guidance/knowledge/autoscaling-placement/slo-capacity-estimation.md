<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# SLO Capacity Estimation

English | [简体中文](slo-capacity-estimation_zh.md)

## Problem and mechanism

Peak tokens/s does not tell an autoscaler how many requests a replica can serve while meeting both time-to-first-token (TTFT) and inter-token latency. Capacity must be conditioned on model, device, batching, lengths, cache reuse, and the target percentile. A controller that sizes only decode throughput can leave prefill queueing unprotected.

Measure a service curve over arrival rate λ. Define `μ_SLO = sup{λ: required latency and success constraints hold}` for the chosen workload. An initial replica target is `ceil(λ_demand/μ_SLO)`, but real load balance, cache fragmentation and starts mean this is not a guarantee. For split serving, estimate separate P/D capacities and include transfer in the first-token budget.

An illustrative model needs 20 ms of isolated prompt processing under a 100 ms TTFT target. Spending the entire remaining 80 ms on queueing leaves no margin for routing, transfer or variation. A faster mean decode does not repair that budget. Equally, replacing a percentile target with mean TTFT can hide a small class of very long requests.

The 2026 queueing-model paper uses `T(i)=α+iδ` for iteration time at occupancy i. Its marginal work δ includes compute and KV access over input/output lengths. A state-dependent birth–death chain predicts occupancy, queue delay and mean TTFT/ITL. This is a compact calibration method, not a tail-latency oracle: Poisson arrivals, mean lengths and light/moderate-load validation limit the estimate near saturation.

## Hardware, dtype and evidence

[An Approximate Queueing Model](https://arxiv.org/html/2609.20957v1) evaluates BF16 Llama-3.1-8B and Qwen2.5-14B on H100 with vLLM, batch limit 256 and token budget 8192. It reports mean ITL errors around 5%/8% and larger mean TTFT errors around 14%/16%. Its autoscaling comparison misses fewer target cycles while using more replicas; the result is not a claim of free throughput or superiority over every upstream controller.

Memory limits can dominate a calibrated compute curve. KV dtype, full-attention versus hybrid cache groups, TP replication and long outputs alter resident capacity. FP8 weight GEMM speedups should not be transferred into a BF16-KV latency model without recalibration. Profiling costs are paid per meaningful model/device/runtime configuration, not merely per model name.

## Public implementation and current scope

Checked 2026-10-14. Dynamo's [planner README](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/README.md) and [throughput code](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py) already use engine-capacity models for TTFT/ITL, including prefill cache-hit inputs and decode acceptance length. Model-not-ready observations hold capacity rather than inventing a rate.

llm-d's [SLO guide](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/slo-aware/README.md) and [recording rules](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/slo-aware/prometheus-rule.yaml) use `max(P90_TTFT/S_TTFT, P90_TPOT/S_TPOT)`, clamp each sample before 45-second smoothing, then drive KEDA with a dead band and pending-capacity credit. The guide is explicitly one variant/one SLO pair; P/D adaptation is future work there. Predicted per-request latency is not a future traffic forecast.

Foretoken's [autoscaling guide](../../../../docs/autoscaling.md) and [token-load decision](../../../../control-plane/internal/autoscaling/algorithm/decision/token_load.go) provide queue/token policies, not the above calibrated SLO-capacity estimator. The architecture already separates recommendations from controller lifecycle; a future estimator belongs in that decision boundary, not a second controller.

## Experiments and remaining questions

Fit a small service model from one subset of measured points; hold out lengths, hit rates and rates. Compare mean prediction error separately from required percentile error. Include the saturation knee and heavy-tailed mixtures; a model accurate at light load may fail precisely where scaling matters.

Run the real service under steady, ramp and burst arrivals. Compare queue scaling, calibrated capacity sizing and latency feedback at equal budget bounds. Record completed-request SLO attainment, errors, ready capacity, GPU-seconds and model residuals. Preserve unserved requests in the denominator. Whether online regression can adapt to cache/length drift before tail failures, and how to jointly estimate P/D/transfer capacity, remain open questions. Simulation practice is in [measurement and simulation](../measurement-simulation/README.md).

[Back to autoscaling and placement](README.md)
