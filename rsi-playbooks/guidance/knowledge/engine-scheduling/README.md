<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Engine Scheduling

English | [简体中文](README_zh.md)

Choose what runs in each inference iteration, balancing prefill progress, token delivery, KV capacity, and shared service.

- [Limit Decode Stalls Through Token-Budgeted Prefill Chunks](limit-decode-stalls-through-budgeted-prefill-chunks.md): how much prefill can share a decode iteration without violating token-delivery objectives?
- [Improve SLO Attainment: Batch Sizing and Decode Cadence](improve-slo-attainment-batch-sizing-and-decode-cadence.md): when should requests with different TTFT/TPOT objectives receive different execution frequencies?
- [Avoid KV Thrashing Through Memory-Aware Batch Selection](avoid-kv-thrashing-through-memory-aware-batch-selection.md): why does an initially feasible running set later thrash, and when is smaller admission better than recovery?
- [Balance Token Service: Weighted Counters and Locality-Aware Deficits](balance-token-service-weighted-counters-and-locality-deficits.md): how do weighted token service and cache-local deficits differ from equal request counts?
- [Reduce MoE Weight Traffic Through Layered Prefill](reduce-moe-weight-traffic-through-layered-prefill.md): when can splitting work across layers reduce the repeated expert-weight traffic of small token chunks?

The engine owns batch execution and cache feasibility. [Routing and admission](../routing-admission/README.md) cover ingress waiting, instance selection, and overload decisions; those controls cannot independently enforce an engine's next-token schedule.

Return to [inference knowledge](../README.md).
