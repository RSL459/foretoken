<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Measurement and Simulation

English | [简体中文](README_zh.md)

Choose a comparison that separates competing explanations, with matching workload, timing boundary, population, and numerical semantics.

- [Arrivals and queueing](workload-arrival-queueing.md): distinguish fixed concurrency, externally scheduled arrivals, replay delay, and coordinated omission.
- [Goodput and tail attribution](goodput-tail-attribution.md): measure joint request compliance and explain the requests that actually form the tail.
- [Trace critical paths](trace-critical-path.md): separate duration totals, occupied wall time, resource contention, and causal dependencies.
- [Profile-driven simulation](profile-driven-simulation.md): identify runtime-model versus scheduling-model mismatch and calibrate useful configuration rankings.
- [Numerical and quality divergence](numerical-quality-divergence.md): separate fixed-prefix distributions, greedy instability, and task-level answer quality.

Experiment commands and result layouts belong in the [experiment records guide](../../../experiment-records.md); the broader research process is described in [meta-knowledge](../../meta-knowledge/README.md).

[All inference knowledge](../README.md)
