<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# P/D Cost and Dynamic Allocation

English | [简体中文](pd-cost-and-dynamic-allocation_zh.md)

## Problem and mechanism

A long prefill can delay every decode request sharing an engine. Separating prefill (P) and decode (D) removes that interference and permits different batching and parallelism, but adds another queue, KV transfer, and duplicated weights. The question is whether isolation saves more latency and capacity than those additions consume.

For one request, compare approximate first-token paths:

`T_aggregate = Q_A + P_A + first_decode_A`

`T_split = Q_P + P_P + Q_X + transfer + Q_D + first_decode_D`.

These are accounting expressions, not independent random variables: routing, KV reservation, and batching couple the terms. A useful break-even test is whether the removed interference exceeds the additional transfer and queueing. Strong decode-local prefix reuse can make aggregate execution cheaper even for a long raw prompt.

An illustrative request has 32K input tokens but 31K reusable tokens on D. Its effective prefill is only 1K tokens. Sending the whole request through P may add remote transfer for little saved compute. Conversely, a cold 32K request can monopolize a mixed engine and justify splitting. The decision should use the selected destination's cache state and decode headroom, not only raw input length.

Capacity allocation is a slower decision. With arrival rate λ and calibrated SLO-feasible capacities μ_P and μ_D, initial counts are `n_P = ceil(λ/μ_P)` and `n_D = ceil(λ/μ_D)`. Re-estimate both as lengths, hit rates, and batch occupancy change. Conditional request routing, changing role replica counts, and converting a live worker between roles are three different mechanisms; the first two do not establish the third.

## Hardware and cost conditions

Measure a concrete model, weight dtype, KV dtype, TP layout, and link. For BF16 dense/GQA models, prefill often rewards compute throughput while decode needs HBM bandwidth and KV capacity. MoE and hybrid attention alter that balance. FP8 weights do not imply FP8 KV; transfer bytes follow the actual cache representation.

The extra P worker's GPU-hours, duplicate model residency, connection setup, and retirement time count against split-serving savings. Short inputs, low concurrency, slow host-staged TCP, and large reusable prefixes can favor a well-tuned aggregate engine with chunked prefill. A fixed P:D ratio is not portable across workloads.

## Public implementation and integration scope

Checked 2026-10-14. Dynamo's [conditional disaggregation guide](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/docs/fern/pages/developer-guide/advanced-customizations/conditional-disaggregation.md) documents effective-ISL/load decisions and a decode-busy override for vLLM and TensorRT-LLM, not SGLang. Its [throughput planner](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py) already sizes P/D independently, accounts for model readiness and pending starts, and can establish floors for load scaling. These are current code, not fresh porting opportunities.

llm-d's [prefix-based decider](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/profilehandler/disagg/prefix_based_pd_decider.go) evaluates an `if-available` preference and can return HTTP 412 when the uncached suffix warrants remote prefill. Production Stack's [routing code](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py) contains orchestrated P/D endpoint selection; it is not evidence of live worker-role conversion.

Foretoken's [workflow](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs) already completes P before fresh D selection and retains cross-stage cleanup. Its [autoscaling owner](../../../../control-plane/internal/autoscaling/README.md) evaluates role Pools separately. Neither fact demonstrates the conditional split policy above.

## Discriminating experiments and remaining questions

First replay a queueing model with identical arrival timestamps, joint input/output lengths, hit rates, and transfer costs. Compare fixed ratios, independently scaled roles, and conditional split routing at equal GPU budget. Vary hot-prefix placement separately from offered traffic; otherwise cache warming can masquerade as a scheduling gain.

Then run aggregate chunked-prefill and P/D services using the same checkpoint and output settings. Sweep short/cold, long/cold, and long/hot requests, including bursts during role scaling. Record TTFT and TPOT distributions, successful SLO goodput, transfer delay, ready versus requested capacity, and total GPU-seconds. Inspect whether D saturation or transfer replaces P interference as the bottleneck. Joint decisions under stale cache/load observations and expensive role transitions remain useful research questions.

[Back to disaggregated serving](README.md)
