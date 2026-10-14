<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce serving cost through profiled heterogeneous stage placement

English | [简体中文](reduce-serving-cost-through-profiled-heterogeneous-stage-placement_zh.md)

## Problem and mechanism

The accelerator with the highest peak FLOPs is not necessarily the cheapest device for every inference stage. Prefill, decode attention and MoE experts have different compute, bandwidth and memory needs. Heterogeneous placement assigns a stage to a suitable device without assuming that all stages can share arbitrary kernels or cache representations.

Start with a feasibility matrix: model stage × accelerator × dtype × parallelism. Reject combinations that cannot load weights, hold required state, execute the necessary operators, or exchange state through the supported connector. For each feasible combination, measure capacity under its stage latency budget. Only then optimize cost; unsupported combinations are not slow candidates.

A simple objective is `min Σ_s,h n_s,h*c_h`, subject to stage capacity, memory, transfer and end-to-end SLO constraints. Here n_s,h is the integer worker count for stage s on hardware h, and c_h is measured rental or amortized operating cost per worker, including the relevant host/network share. For AFD, attention capacity often follows HBM bandwidth and KV residency, while sufficiently batched experts benefit from compute. For P/D, a compute-rich P device can serve several bandwidth-rich D devices, provided KV handoff remains affordable.

An illustrative allocation uses one P worker at 8 requests/s and two D workers at 4 requests/s each. Replacing P with a cheaper 5-request/s device lowers the fleet's sustainable rate to 5 despite unchanged D capacity. Replacing D with smaller-memory devices can instead reduce resident concurrency and violate TPOT. Optimize the complete path rather than selecting the lowest price for each isolated kernel.

## Hardware, models, dtype and costs

[MegaScale-Infer](https://arxiv.org/html/2504.02263) studies BF16 weights, activations and KV for Mixtral-8×22B, DBRX and a scaled MoE. It uses H20 for attention and L40S for experts, exploiting different bandwidth/compute-per-cost profiles. The paper's normalized purchase prices are historical inputs, not current cloud prices. Its decode-only measurements temporally separate prefill; end-to-end gains are reported separately.

[FastAFD](https://haoailab.com/blogs/fastafd/) physically evaluates FP8 MoE on GB200 NVL72. Its projections for future Rubin plus LPX/LPU hardware are projections, not validated heterogeneous deployment. FP8 weight support does not establish compatible KV transfer, and moving attention or FFN across different vendors requires actual runtime and numerical support—not just matching tensor dimensions.

Account for duplicate weights, conversion, host staging, graph warmup, network allocation and underfilled expert batches. A lower-cost device that needs more TP ranks can incur extra synchronization and consume scarcer topology. Power caps may also change effective clocks and shift the best ratio; static device specifications are insufficient.

## Public implementation and current scope

AIBrix's [optimizer](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/python/aibrix/aibrix/gpu_optimizer/optimizer/optimizer.py) maps workload signatures to throughput bins. Its [Melange solver](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/python/aibrix/aibrix/gpu_optimizer/optimizer/solver/melange/solver.py) minimizes GPU cost with integer replica counts and workload-slice assignment constraints.

Dynamo's [planner](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py) already makes separate P/D capacity decisions. llm-d's [Kueue rebalancing guide](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/kueue-rebalancing/README.md) implements quota admission and borrowing, not stage-specific execution modeling or KV migration.

Foretoken's [E/P/D example](../../../../examples/encoder-prefill-decode/README.md) permits stage resource and engine-argument choices. Device-specific execution details belong in [heterogeneous hardware](../heterogeneous-hardware/README.md).

## Experiments and remaining questions

First profile the actual stage/device matrix, with equal model outputs and explicit weight/KV dtypes. Use measured service curves and transfer costs in a small integer allocation search. Compare uniform hardware, independently cheapest stages and jointly optimized stages at the same budget. Include a capacity-loss sensitivity study so noisy profiling does not dictate a fragile plan.

Then serve trace-driven requests on the selected homogeneous and heterogeneous deployments. Record SLO goodput, per-stage queueing, GPU-hours, network cost and power where measured. Change length mix and hit rate after deployment to expose profile drift. Keep the exact checkpoint and numerical validation constant; otherwise a quantization change can look like a placement gain. Remaining work includes online reallocation with startup/drain costs, robust tail estimates and supported cross-hardware state exchange.
[Back to disaggregated serving](README.md)
