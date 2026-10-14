<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Routing and Admission

English | [简体中文](README_zh.md)

Decide which arrivals can use shared serving capacity, how long they can wait, and which instance should execute them.

- [Cache affinity versus queueing cost](cache-affinity-versus-queue.md): when does waiting for a warm worker cost more than recomputing on a less-loaded one?
- [Predictive load routing and observation delay](predictive-load-routing.md): how should predicted work, unseen dispatches, and missing latency predictions affect selection?
- [Deadline-aware admission and goodput](deadline-aware-admission.md): when is rejecting infeasible work more useful than forwarding it, and how should all arrivals be counted?
- [Tenant queues and overload dispatch](tenant-queues-and-overload.md): how do priority, fairness, shared capacity, and session progress interact during a burst?

These decisions belong to the request layer. [Engine scheduling](../engine-scheduling/README.md) owns actual batch membership and token service; cluster orchestration owns capacity and placement changes.

Return to [inference knowledge](../README.md).
