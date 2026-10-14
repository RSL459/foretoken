<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# MoE Execution

English | [简体中文](README_zh.md)

Choose an entry by the work that delays an expert layer.

- Are gathering and activation traffic more expensive than the matrix multiply? [Grouped GEMM without unnecessary token materialization](tile-aware-grouped-gemm.md) explains gather fusion, asynchronous output stores, and why token-rounding training is not an unchanged-router inference optimization.
- Does a throughput-oriented kernel regress at low load? [Small-batch work partition](small-batch-megakernel-scheduling.md) separates live tokens from workspace capacity and compares split execution with persistent megakernel roles.
- Do persistent hot experts or workload changes create slow ranks? [Windowed expert rebalancing](windowed-expert-rebalancing.md) follows observation, replication, migration, and activation of new mappings.
- Is the current batch imbalanced despite a sensible placement? [Online replica token assignment](online-replica-token-assignment.md) explains LPLB's constrained redistribution and the planning-overhead break-even question.
- Does low precision improve bytes but change answers or backend eligibility? [Quantized MoE layouts](quantized-moe-layouts.md) connects packed weights, scale layouts, activation conversion, and reduction semantics.

For expert placement, dispatch, TP/CP/PP, and overlap, continue with [parallelism and communication](../parallelism-communication/README.md). Full-model validation uses the maintained [deployment recipes](../../../../examples/recipes/README.md), [performance evaluation](../../../../benchmarks/docs/perf/README.md), [quality evaluation](../../../../benchmarks/docs/eval/README.md), and [profiling](../../../../benchmarks/docs/profile/README.md). Measure unprofiled service behavior separately from diagnostic captures.

Return to [inference knowledge](../README.md).
