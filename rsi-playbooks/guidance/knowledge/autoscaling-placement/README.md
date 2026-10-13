<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Autoscaling and Placement

English | [简体中文](README_zh.md)

A replica recommendation is useful only when the chosen hardware, readiness delay, routing state, and retirement path can deliver the requested capacity.

- How many replicas meet the workload's latency targets? [SLO capacity estimation](slo-capacity-estimation.md) combines calibrated service models with live feedback without confusing average predictions with percentile guarantees.
- Why does scaling arrive after the burst? [Predictive scaling and cold start](predictive-scaling-and-cold-start.md) matches forecast horizon to actuation delay and accounts for capacity already starting.
- Why do equal request counts need different GPU capacity? [Token-load state](token-load-state.md) separates uncached prefill work, decode activity, KV occupancy, queued demand, and model-relative service deficits.
- Where should new capacity go when caches and links are shared? [Topology and cache placement](topology-and-cache-placement.md) evaluates placement and routing together, including contention and warm-state loss.
- How can a busy worker be removed without losing generations? [Drain and state migration](drain-and-state-migration.md) distinguishes route withdrawal, natural completion, request migration, and shared-cache cleanup.

For execution-stage partitioning and transfer costs, see [disaggregated serving](../disaggregated-serving/README.md). Other mechanisms remain accessible through [inference knowledge](../README.md).

## Evidence scope

Implementation checks are dated 2026-10-14.

The inspected snapshots are Dynamo `b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd`, llm-d `277b34d062ff954435cf8b1b05efbd75090cf788`, llm-d inference scheduler `5253f55516f496129248766d1e4b745daba68887`, AIBrix `d0500b0399cf35ad0bf95d073faa83c23308f463` (all 2026-10-13), Production Stack `4e076e8de3698a3729b575e3a5ade65ffbb929cf` (2026-10-07), and Foretoken `e6ae3df6d02a72f4bbec3050c4291c1489c1bc07`.

[Back to inference knowledge](../README.md)
