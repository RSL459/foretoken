<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Disaggregated Serving

English | [简体中文](README_zh.md)

Choose an execution boundary by its saved work, transferred state, and latency budget—not by the number of independently deployed workers.

- When does separating prefill and decode pay? [P/D cost and dynamic allocation](pd-cost-and-dynamic-allocation.md) compares interference savings with transfer, queueing, and role-change costs, distinguishing conditional routing from worker conversion.
- Can attention workers share an expert pool efficiently? [Attention–FFN disaggregation](attention-ffn-disaggregation.md) explains FastAFD's microbatch execution, memory benefit, collective ordering, and hardware-dependent balance.
- Why does one faster stage fail to improve the service? [Multistage resource balance](multistage-resource-balance.md) allocates encoder, prefill, transfer, and decode capacity around the end-to-end critical path.
- Why does KV transfer stall despite a fast link? [Transfer and network bottlenecks](transfer-network-bottlenecks.md) quantifies KV bytes, fan-in, staging, layout conversion, and completion lifetime.
- Which accelerator should execute each stage? [Heterogeneous stage placement](heterogeneous-stage-placement.md) compares feasible stage/device combinations by SLO goodput and total cost.

For capacity controllers, cache-aware placement, and retirement, continue with [autoscaling and placement](../autoscaling-placement/README.md). Encoder execution and multimodal input details belong in the [multimodal knowledge](../multimodal-generation/README.md).

## Evidence scope

Implementation checks are dated 2026-10-14.

Snapshots inspected:

- Dynamo `b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd` (2026-10-13).
- llm-d `277b34d062ff954435cf8b1b05efbd75090cf788` and inference scheduler `5253f55516f496129248766d1e4b745daba68887` (2026-10-13).
- AIBrix `d0500b0399cf35ad0bf95d073faa83c23308f463` (2026-10-13).
- Production Stack `4e076e8de3698a3729b575e3a5ade65ffbb929cf` (2026-10-07).
- FastAFD `3c7161949310b6d59d6b4cf9bf997a4935c8113b` (2026-07-08).
- Foretoken `e6ae3df6d02a72f4bbec3050c4291c1489c1bc07`.

[Back to inference knowledge](../README.md)
