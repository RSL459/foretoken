<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Measurement and Simulation

English | [简体中文](README_zh.md)

Choose a comparison that separates competing explanations, with matching workload, timing boundary, population, and numerical semantics.

- [Diagnose hidden queueing through arrival-relative latency measurement](diagnose-hidden-queueing-through-arrival-relative-latency-measurement.md): distinguish fixed concurrency, externally scheduled arrivals, replay delay, and coordinated omission.
- [Diagnose SLO failures through request-level compliance attribution](diagnose-slo-failures-through-request-level-compliance-attribution.md): measure joint request compliance and explain the requests that actually form the tail.
- [Diagnose latency bottlenecks through causal trace-path reconstruction](diagnose-latency-bottlenecks-through-causal-trace-path-reconstruction.md): separate duration totals, occupied wall time, resource contention, and causal dependencies.
- [Diagnose simulation mismatch through batch and arrival replay](diagnose-simulation-mismatch-through-batch-and-arrival-replay.md): identify runtime-model versus scheduling-model mismatch and calibrate useful configuration rankings.
- [Diagnose generation divergence through fixed-prefix and task comparisons](diagnose-generation-divergence-through-fixed-prefix-and-task-comparisons.md): separate fixed-prefix distributions, greedy instability, and task-level answer quality.

Experiment commands and result layouts belong in the [experiment records guide](../../../experiment-records.md); the broader research process is described in [meta-knowledge](../../meta-knowledge/README.md).

[All inference knowledge](../README.md)
