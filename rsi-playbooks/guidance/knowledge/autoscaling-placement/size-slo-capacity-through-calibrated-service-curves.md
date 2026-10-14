<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Size SLO capacity through calibrated service curves

English | [简体中文](size-slo-capacity-through-calibrated-service-curves_zh.md)

## Problem and mechanism

Peak tokens/s does not tell an autoscaler how many requests a replica can serve while meeting both time-to-first-token (TTFT) and inter-token latency. Capacity must be conditioned on model, device, batching, lengths, cache reuse, and the target percentile. A controller that sizes only decode throughput can leave prefill queueing unprotected.

Measure a single-replica service curve over arrival rate λ in requests/s. Define `μ_SLO = sup{λ: required latency and success constraints hold}` for the chosen workload; λ_demand is the total offered request rate. An initial replica target is `ceil(λ_demand/μ_SLO)`, but real load balance, cache fragmentation and starts mean this is not a guarantee. For split serving, estimate separate P/D capacities and include transfer in the first-token budget.

An illustrative model needs 20 ms of isolated prompt processing under a 100 ms TTFT target. Spending the entire remaining 80 ms on queueing leaves no margin for routing, transfer or variation. A faster mean decode does not repair that budget. Equally, replacing a percentile target with mean TTFT can hide a small class of very long requests.

The 2026 queueing-model paper uses `T(i)=α+iδ`: i is the active batch occupancy, α is fixed iteration overhead, and δ is marginal time per active request, including compute and KV access over input/output lengths. The birth–death state counts active plus queued requests; beyond the batch limit B, service uses B active requests. A state-dependent birth–death chain predicts occupancy, queue delay and mean TTFT/ITL. This is a compact calibration method, not a tail-latency oracle: Poisson arrivals, mean lengths and light/moderate-load validation limit the estimate near saturation.

## Hardware, dtype and evidence

[An Approximate Queueing Model](https://arxiv.org/html/2609.20957v1) evaluates BF16 Llama-3.1-8B and Qwen2.5-14B on H100 with vLLM, batch limit 256 and token budget 8192. It reports mean ITL errors around 5%/8% and larger mean TTFT errors around 14%/16%. Its autoscaling comparison misses fewer target cycles while using more replicas.

Memory limits can dominate a calibrated compute curve. KV dtype, full-attention versus hybrid cache groups, TP replication and long outputs alter resident capacity. FP8 weight GEMM speedups should not be transferred into a BF16-KV latency model without recalibration. Profiling costs are paid per meaningful model/device/runtime configuration, not merely per model name.

## Public implementation and current scope

Dynamo's [planner README](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/README.md) and [throughput code](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py) already use engine-capacity models for TTFT/ITL, including prefill cache-hit inputs and decode acceptance length. Model-not-ready observations hold capacity rather than inventing a rate.

llm-d's [SLO guide](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/slo-aware/README.md) and [recording rules](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/slo-aware/prometheus-rule.yaml) use `max(P90_TTFT/S_TTFT, P90_TPOT/S_TPOT)`, where S_TTFT and S_TPOT are the latency targets. The recording rules prefer predicted latency histograms and fall back to measured ones, computing P90 over a one-minute rate window. They cap pressure at 2 before 45-second smoothing, then drive KEDA with a dead band and pending-capacity credit. The guide is explicitly one variant/one SLO pair; P/D adaptation is future work there.

Foretoken's [autoscaling guide](../../../../docs/autoscaling.md) and [token-load decision](../../../../control-plane/internal/autoscaling/algorithm/decision/token_load.go) provide queue/token policies, not the above calibrated SLO-capacity estimator. The architecture already separates recommendations from controller lifecycle; a future estimator belongs in that decision boundary, not a second controller.

## Experiments and remaining questions

Fit a small service model from one subset of measured points; hold out lengths, hit rates and rates. Compare mean prediction error separately from required percentile error. Include the saturation knee and heavy-tailed mixtures; a model accurate at light load may fail precisely where scaling matters.

Run the real service under steady, ramp and burst arrivals. Compare queue scaling, calibrated capacity sizing and latency feedback at equal budget bounds. Record SLO attainment over all offered arrivals, qualified completions per second, errors, ready capacity, GPU-seconds and model residuals. Whether online regression can adapt to cache/length drift before tail failures, and how to jointly estimate P/D/transfer capacity, remain open questions. Simulation practice is in [measurement and simulation](../measurement-simulation/README.md).

[Back to autoscaling and placement](README.md)
