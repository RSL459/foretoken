<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Deadline-Aware Admission and Goodput

English | [简体中文](deadline-aware-admission_zh.md)

Selecting the least-bad worker is different from deciding that a request can still meet its objective. During overload, forwarding every arrival can consume GPU time on doomed work while making otherwise feasible requests late. Admission asks whether to run, wait, or reject; routing asks where eligible work should run.

## Existing controls are not interchangeable

llm-d currently implements request admission and flow-control queues. Its inspected `admission.go` has a legacy saturation check that rejects sheddable negative-priority requests at saturation, and a flow-control path that waits for dispatch, rejection, TTL expiry, cancellation, or shutdown. That file does not perform a predictive deadline-feasibility test.

llm-d separately implements predicted TTFT/TPOT headroom in latency scoring. When every prediction is unfavorable, its scorer can still select an idle or least-deficit candidate. A low score is not a rejection decision. Production Stack already routes by priority and forwards the resolved priority to the engine, but its priority-routing implementation does not constitute a predicted-deadline admission controller. Foretoken already has role-based waiting, concurrency accounting, queue timeout, and request-deadline outcomes. Feasibility-aware coordination builds on these queue and timeout controls.

## Follow a deadline from ingress

A request arrives at time zero with a 300-ms TTFT objective. Input preparation and ingress waiting consume 100 ms. Its best candidate has an estimated 120-ms worker wait and 100-ms prefill. Only 200 ms remain, but estimated downstream work is 220 ms. Giving the worker a fresh 300-ms timeout would hide the 100 ms already consumed.

An illustrative feasibility check is:

`remaining_slack = arrival_deadline - now - estimated_downstream_latency`.

A negative value suggests the request cannot meet the current objective, subject to estimation error and permitted alternatives. If the objective is TTFT, use first-token work; if it is end-to-end completion, include generation. A request deadline, queue TTL, TTFT objective, and TPOT objective are separate contracts. Averaging them into one “latency” value makes the decision ambiguous.

SCORPIO's 2026 revision combines TTFT prediction with rejection, deadline ordering of waiting requests, and a TPOT admission test. The latter uses a virtual batch size derived from heterogeneous token-rate requirements, checking predicted TPOT against the strictest target in the resulting running set. Its decode credit mechanism then attempts to supply those differentiated rates. Admission and batch execution share the same latency model and decode-rate assumptions. Calibrate them for the model, weight/cache dtype, backend, topology, and parallelism configuration.

## Count qualified completions and all arrivals

For a fixed observation window, a useful service metric is `goodput = completed requests meeting all declared SLOs / elapsed time`. Also report attainment over all offered arrivals, counting rejection and timeout as unmet unless the benchmark explicitly defines another contract. SCORPIO counts rejected requests as SLO-unmet in adherence calculations.

Imagine 1,000 arrivals: policy A completes 900, of which 500 meet SLO; policy B rejects 300 and completes 700, of which 650 meet SLO. B has higher qualified completions, but its admitted-only attainment of 93% must not be compared with A's arrival-based attainment of 50%. Report both denominators and all outcomes. Admission is useful when rejecting infeasible work preserves more useful completions, not when it merely removes failures from the report.

## Ownership, trade-offs, and implementation direction

The request layer owns original arrival time, trusted service objectives, ingress queue state, and response outcomes. The engine owns execution feasibility and batch membership. Cluster orchestration owns slower capacity response. Foretoken should preserve those owners and propagate remaining budget, not reset the timing origin at each stage or let a scorer mutate global admission capacity.

Prediction error causes false rejection or overload. Aggressive rejection can disadvantage long prompts, stricter classes, or a tenant whose workload is unfamiliar to the model. Waiting can help a short transient burst but harm an already-tight deadline. Cancellation after dispatch must release request accounting, while engine resource release remains asynchronous and engine-owned.

## Experiment and open question

Use an open-loop arrival trace whose rate crosses capacity and then recovers. Mix tight/loose TTFT classes and different output lengths. Compare existing bounded waiting, deadline ordering, and prediction-aware admission while holding engine scheduling constant; then separately test coordinated engine cadence.

Measure arrival-based SLO attainment, qualified completions per second, false-rejection estimates, per-class outcomes, queue residence, deadline expiry location, p99 token gaps, and recovery after the burst. Include underprediction and overprediction experiments. Retain raw request outcomes so a policy cannot improve a summary by dropping late results.

The unresolved question is whether a calibrated downstream-feasibility model adds useful completions beyond current queue/concurrency controls.

## Sources

Checked 2026-10-14.

- [SCORPIO, 2505.23022v2, 2026-08-26](https://arxiv.org/html/2505.23022v2): coordinated TTFT/TPOT admission and rejected-request accounting.
- [llm-d admission code, commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/requestcontrol/admission.go).
- [llm-d latency scorer, same revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/scorer/latency/plugin.go): ranking is not rejection.
- [Production Stack routing, commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py): implemented priority forwarding.
- [Foretoken admission](../../../../data-plane/frontend/src/admission/src/lib.rs) and [arrival capture](../../../../data-plane/frontend/src/server/src/admission.rs): current outcome and timing boundaries.
