<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Engine Scheduling

English | [简体中文](README_zh.md)

Choose what runs in each inference iteration, balancing prefill progress, token delivery, KV capacity, and shared service.

- [Token budgets and chunked prefill](token-budget-and-chunking.md): how much prefill can share a decode iteration without violating token-delivery objectives?
- [SLO-aware batch selection](slo-aware-batch-scheduling.md): when should requests with different TTFT/TPOT objectives receive different execution frequencies?
- [KV pressure, preemption, and recompute](preemption-and-recompute.md): why does an initially feasible running set later thrash, and when is smaller admission better than recovery?
- [Fair service under continuous batching](service-fairness.md): how do weighted token service and cache-local deficits differ from equal request counts?
- [Layer-group prefill for MoE](layered-prefill.md): when can splitting work across layers reduce the repeated expert-weight traffic of small token chunks?

The engine owns batch execution and cache feasibility. [Routing and admission](../routing-admission/README.md) cover ingress waiting, instance selection, and overload decisions; those controls cannot independently enforce an engine's next-token schedule.

Return to [inference knowledge](../README.md).
