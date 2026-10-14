<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Autoscaling and Placement

English | [简体中文](README_zh.md)

A replica recommendation is useful only when the chosen hardware, readiness delay, routing state, and retirement path can deliver the requested capacity.

- How many replicas meet the workload's latency targets? [Size SLO capacity through calibrated service curves](size-slo-capacity-through-calibrated-service-curves.md) combines calibrated service models with live feedback and distinguishes mean predictions from percentile targets.
- Why does scaling arrive after the burst? [Anticipate capacity demand through startup-aware token forecasting](anticipate-capacity-demand-through-startup-aware-token-forecasting.md) matches forecast horizon to actuation delay and accounts for capacity already starting.
- Why do equal request counts need different GPU capacity? [Size replicas through uncached-token and KV pressure](size-replicas-through-uncached-token-and-kv-pressure.md) separates uncached prefill work, decode activity, KV occupancy, queued demand, and model-relative service deficits.
- Where should new capacity go when caches and links are shared? [Reduce request latency through topology-aware cache placement](reduce-request-latency-through-topology-aware-cache-placement.md) evaluates placement and routing together, including contention and warm-state loss.
- How can a busy worker be removed without losing generations? [Preserve active generations through draining and state handoff](preserve-active-generations-through-draining-and-state-handoff.md) distinguishes route withdrawal, natural completion, request migration, and shared-cache cleanup.

For execution-stage partitioning and transfer costs, see [disaggregated serving](../disaggregated-serving/README.md). Other mechanisms remain accessible through [inference knowledge](../README.md).

[Back to inference knowledge](../README.md)
