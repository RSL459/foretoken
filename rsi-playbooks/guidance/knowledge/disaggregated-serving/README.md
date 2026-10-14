<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Disaggregated Serving

English | [简体中文](README_zh.md)

Choose an execution boundary by its saved work, transferred state, and latency budget—not by the number of independently deployed workers.

- When does separating prefill and decode pay? [Reduce prefill/decode interference through conditional stage separation](reduce-prefill-decode-interference-through-conditional-stage-separation.md) compares interference savings with transfer, queueing, and role-change costs, distinguishing conditional routing from worker conversion.
- Can attention workers share an expert pool efficiently? [Increase expert batch utilization through attention–FFN disaggregation](increase-expert-batch-utilization-through-attention-ffn-disaggregation.md) explains FastAFD's microbatch execution, memory benefit, collective ordering, and hardware-dependent balance.
- Why does one faster stage fail to improve the service? [Prevent pipeline backlogs through joint stage-capacity allocation](prevent-pipeline-backlogs-through-joint-stage-capacity-allocation.md) allocates encoder, prefill, transfer, and decode capacity around the end-to-end critical path.
- Why does KV transfer stall despite a fast link? [Diagnose KV handoff stalls through fan-in transfer profiling](diagnose-kv-handoff-stalls-through-fan-in-transfer-profiling.md) quantifies KV bytes, fan-in, staging, layout conversion, and completion lifetime.
- Which accelerator should execute each stage? [Reduce serving cost through profiled heterogeneous stage placement](reduce-serving-cost-through-profiled-heterogeneous-stage-placement.md) compares feasible stage/device combinations by SLO goodput and total cost.

For capacity controllers, cache-aware placement, and retirement, continue with [autoscaling and placement](../autoscaling-placement/README.md). Encoder execution and multimodal input details belong in the [multimodal knowledge](../multimodal-generation/README.md).

[Back to inference knowledge](../README.md)
