<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Avoid Tenant Starvation: Fair Queues and Bounded Dispatch

English | [简体中文](avoid-tenant-starvation-fair-queues-and-bounded-dispatch_zh.md)

A shared request queue can let a bursty tenant occupy every waiting position. A single global priority order can starve low-priority traffic even when individual requests are small. Multi-tenant overload control needs an explicit sharing objective, bounded waiting, and a lifecycle that releases capacity when a request stops consuming it.

## Separate four decisions

Priority expresses which class can proceed first. Fairness expresses how eligible flows share service. Capacity limits bound active work. Queue expiry says how long waiting remains useful. None implies the others: a priority integer does not reserve capacity, and selecting the oldest head across all queues does not establish tenant fairness.

Current llm-d has per-flow queue interfaces, ordering plugins, fairness plugins, and priority holdback. Its `globalstrict` documentation says it selects the best queue head across flows within a priority band and offers no tenant fairness. Its program-aware plugin provides least-attained-service (LAS) or turn-priority. Its priority-holdback plugin gates lower-priority dispatch earlier as saturation rises, with configurable priority ceilings.

AIBrix has per-user estimated-token VTC routing, but the cited basic router selects pods and updates estimated usage; it does not perform capacity rejection or reconcile actual generated tokens in that file. Production Stack resolves request priority, selects endpoints, and forwards priority; its documentation/code distinction between router selection and engine scheduling matters. Foretoken already owns role-based waiting and fair dispatch separately from routing, so a candidate should refine that owner rather than add another queue in a scorer.

## A burst through the queues

Suppose tenant A enqueues 1,000 requests and tenant B enqueues one. A FIFO global queue can make B wait behind the entire burst. Per-tenant queues let a dispatcher compare queue heads rather than every queued item. LAS can favor the flow with less attained weighted token service; request round-robin gives equal dispatch counts but ignores large differences in execution cost.

llm-d's program-aware LAS applies decayed service, with output tokens weighted twice input tokens in its documented mechanism. Decay makes recent consumption more important than ancient history. Turn-priority instead favors deeper sessions while incorporating waiting time. This can shorten an interactive program's next dependent turn, but it is a different objective from equal tenant service. Its documentation requires one fairness ID per session for turn depth to be meaningful.

VTC's original service counters prevent idle clients from returning with unlimited credit. DLPM's locality-aware deficit method adds a quantum that permits cache-friendly runs while bounding domination. The papers bound engine-level service; gateway-local dispatch counters measure a different scope. See [engine fairness](../engine-scheduling/balance-token-service-weighted-counters-and-locality-deficits.md) for that distinction.

## Identity and capacity scope

The fairness identity must come from the deployment's trusted identity boundary. An arbitrary caller-controlled ID can split one tenant into many apparent flows. Conversely, sending all missing identities to one default flow makes those callers share one queue. llm-d explicitly documents the default-flow and session-depth consequences.

Multiple frontends also change the scope: two independent queues with local counters can each consider the same tenant underserved. Decide whether the product promises fairness per frontend, service, tenant, or session. Reuse the existing admission/request-ledger owner when shared capacity is required; do not make Prometheus the transaction system for admission.

The request layer owns queueing, identity, capacity reservations, expiry, and dispatch. The engine owns batch membership and actual token service. Cluster orchestration owns replica creation and removal. A disconnected client or abandoned in-flight request must not retain dispatch accounting indefinitely; llm-d's program-aware documentation identifies this state-retention issue explicitly. Physical GPU cleanup still follows the engine lifecycle.

## Experiment and remaining design choice

Create a fixed-rate tenant, a bursting tenant, a long-output tenant, and dependent multi-turn sessions. Run all against the same service capacity. Compare current fair dispatch, strict global ordering, LAS, and a session-oriented candidate only when those objectives match the workload. Keep identity and priority assignment constant across comparisons.

Report per-tenant queue residence, rejection/expiry/cancellation, weighted service, worst-tenant TTFT/TPOT attainment, overall goodput, and burst-recovery time. For multi-turn workloads, also report program completion time: faster individual requests may not shorten the program. Add cancellation and lost-completion scenarios to inspect outstanding accounting, and disclose the scope of all counters.

The remaining choice is not “which queue algorithm wins” in isolation. It is which product objective should hold under overload, and whether dispatch and engine execution jointly implement it without losing useful work or starving a class.

## References

- [llm-d global-strict policy, commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/fairness/globalstrict/README.md).
- [Program-aware fairness, same revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/fairness/program-aware/README.md).
- [Priority holdback, same revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/usagelimits/priorityholdback/README.md).
- [AIBrix VTC basic, commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/plugins/gateway/algorithms/vtc/vtc_basic.go) and [Production Stack routing, commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py).
- [VTC methods](https://arxiv.org/html/2401.00588v2) and [DLPM/D2LPM, 2501.14312v1](https://arxiv.org/html/2501.14312v1).
- [Foretoken admission owner](../../../../data-plane/frontend/src/admission/src/lib.rs).
