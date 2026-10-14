<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Fair Service Under Continuous Batching

English | [简体中文](service-fairness_zh.md)

Equal request counts do not imply equal service. A client submitting long generations can consume far more inference work than another submitting short prompts. Continuous batching adds a second complication: once a long request is running, fair admission alone cannot retract the service it receives on every decode step.

## Define what is being shared

Virtual Token Counter (VTC) measures weighted token service rather than requests. In its basic model, `service = wp × input_tokens + wq × output_tokens`. Output tokens can carry a greater weight because decode has a different execution cost. These weights are a policy and cost approximation, not a universal conversion into GPU milliseconds.

When capacity becomes available, VTC admits a request from the queued client with the smallest counter. Prompt processing charges input service; each generated token charges output service. When a client adds its first waiting request, its counter becomes the maximum of its retained value and the minimum counter among clients already waiting. If the waiting queue was empty, the comparison uses the last client that left it. This lift prevents idle time from creating extra credit while preserving service already charged; running clients without queued requests are not the comparison set.

For example, with weights 1 and 2, client A's 1,000-token input and 100-token output cost 1,200 units. Client B's 100-token input and 1,000-token output cost 2,100. A request-count policy calls these equal; VTC does not. The paper's bounded-service-difference result assumes bounded inputs and batches, positive server capacity, and no preemption. It is not a hard per-request latency guarantee.

## Locality changes the objective

VTC's token order can disrupt prefix reuse. The 2025 Locality-aware Fair Scheduling paper introduces DLPM: favor longest-prefix matches, but admit a client only while its deficit is positive. Once every queued client has a nonpositive deficit, replenish active clients whose deficit is nonpositive with a service quantum. Charge uncached input extension and generated output against that credit. Thus a client can receive a cache-local run of work without taking unlimited service.

The choice of accounting is consequential. Charging all input tokens treats long cache-hot prompts as expensive even when they require little new prefill. Charging only the uncached extension measures executed work more closely but gives cache-hot clients more logical tokens for the same share. Neither definition is automatically correct: decide whether fairness concerns computational service, delivered tokens, or a commercial entitlement.

DLPM's service bound depends on request cost and quantum; larger quanta improve locality but allow larger short-term disparities. Its distributed extension, D2LPM, adds client-worker deficits and cache-aware candidate selection, while each worker maintains local fairness. Cross-client sharing and dependent program turns are not resolved by the basic paper model.

## Current implementations are different contracts

AIBrix currently has a `vtc-basic` router. The inspected implementation estimates input/output tokens, uses per-user tracked usage with load to select a pod, and charges estimated usage at routing. It does not implement the paper's engine iteration scheduler or actual completion-token reconciliation in that file. Its fairness scope is gateway-local estimated dispatch service.

llm-d's current program-aware fairness plugin offers least-attained-service with decayed weighted token service and a turn-priority strategy. These are dispatch-queue policies. Its documentation explicitly discusses in-flight state and session-identity assumptions. Foretoken also already separates role-based waiting and fair dispatch from instance scoring.

The engine owns actual batch service and token accounting; the request layer owns trusted identity, ingress fairness, and dispatch; cluster orchestration owns capacity. A multi-router service needs an explicit accounting scope. Per-replica counters do not establish a global service bound, and copying counters into a second controller would create a competing owner.

## Experiment and design decision

Use continuously backlogged clients with unequal input/output lengths, plus a client that goes idle and returns. Repeat with shared-prefix traffic and distinct-prefix traffic. Compare request-count admission, weighted-service scheduling, and a locality-aware candidate at identical arrival load and capacity.

Measure per-client weighted service over time, maximum backlogged service difference, p95/p99 waiting time, worst-client SLO attainment, cache reuse, goodput, and scheduler overhead. State whether cached tokens are charged. Include cancellations and predictor error when a gateway uses estimated output lengths. Trace actual generated tokens so fair dispatch is not mistaken for fair execution.

The remaining question is which service definition fits the deployment and how gateway admission cooperates with engine execution. Reuse existing fair queues and lifecycle accounting before adding a second fairness subsystem.

## Sources

Checked 2026-10-14.

- [VTC, arXiv 2401.00588v2](https://arxiv.org/html/2401.00588v2): counter lifting, weighted service, and fairness assumptions.
- [Locality-aware Fair Scheduling, 2501.14312v1, 2025-01-24](https://arxiv.org/html/2501.14312v1): DLPM/D2LPM and deficit/locality trade-offs.
- [AIBrix `vtc_basic.go`, commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/plugins/gateway/algorithms/vtc/vtc_basic.go): actual gateway accounting and pod selection.
- [llm-d program-aware fairness, commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/fairness/program-aware/README.md): current dispatch strategies and state scope.
- [Foretoken routing](../../../../data-plane/frontend/src/router/README.md): admission and instance selection remain separate.
