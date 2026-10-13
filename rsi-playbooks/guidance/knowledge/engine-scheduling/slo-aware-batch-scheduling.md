<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# SLO-Aware Batch Selection

English | [简体中文](slo-aware-batch-scheduling_zh.md)

When requests have different latency objectives, scheduling every active stream in every iteration can waste scarce decode capacity on requests that could safely wait. Conversely, always prioritizing decode can make queued prefills miss first-token deadlines. Batch selection needs to account for both phases and the service each request actually requires.

## Existing mechanisms and the research increment

Current vLLM V1 already supports chunked prefill, priority-dependent preemption, and a `next_decode_eligible_step` check. These are execution mechanisms, not proof of a heterogeneous-SLO optimizer. SOLA studies per-iteration ordering and workload size. SCORPIO's August 2026 revision combines admission, deadline-based queues, and differentiated decode cadence. Their original methods target a more specific objective than merely adding request priority.

SOLA evaluates a historical vLLM 0.4.2 integration. Its findings about that implementation's default ordering must not be presented as the current V1 default.
## How service frequency changes a batch

Suppose one class needs a 50-ms time-per-output-token target and another accepts 100 ms. In SCORPIO, the token requirement proportion is the strictest target divided by a request's target: `TRP = min_target / request_target`. The two classes therefore receive proportions 1 and 0.5. Each request accrues this credit per decode iteration; requests with credit at least one are selected and consume one credit. A relaxed request can appear roughly every other iteration rather than every iteration.

This mechanism works only if the resulting batch duration supports the targets. SCORPIO estimates TPOT using a virtual batch size, the sum of these proportions, and sequence-length information. Credit arithmetic alone cannot make a 90-ms iteration satisfy a 50-ms target. Nor does a mean TPOT guarantee bounded individual token gaps: iteration variation still matters.

For prefill, SCORPIO orders waiting requests by first-token deadline pressure and rejects requests predicted to be infeasible. SOLA takes a different route. It measures the normalized pressure of TTFT and TPOT against their objectives, chooses which latency to improve while constraining the other, and changes phase ordering, request ordering, and iteration workload. If decode has spare latency budget, more prefill can run; if decode is already late, smaller prefill additions preserve generation opportunities. Its fitted execution costs are updated from measured iteration time. Calibration is specific to the model, dtype, backend, topology, and parallelism; online correction does not make those coefficients portable across deployments.

Andes extends the objective beyond average token spacing. It compares delivered-token progress with an expected consumption timeline and estimates the QoE gain of serving a request now rather than later. A stream with useful buffered tokens can wait while an empty-buffer stream catches up. This is appropriate only when the application actually has such consumption semantics; machine-to-machine output may need every token immediately.

## Ownership and trade-offs

The engine owns actual batch membership, decode cadence, prefill progress, memory feasibility, and cancellation. Foretoken's request layer owns ingress identity, queue time, deadline propagation, and instance selection. A router cannot enforce an engine's next-token deadline merely by attaching a priority integer. Cluster orchestration supplies capacity, but cannot repair a missed millisecond-scale iteration after the fact.

Skipping decode iterations can lower contention, yet increases gap variance and changes how many KV-resident requests compete for memory. Length prediction errors distort future memory and latency estimates. An optimizer of aggregate SLO attainment can sacrifice a small class unless class-level objectives or fairness are explicit. When load is feasible and objectives homogeneous, a simpler decode-first budget may already be sufficient.

## A discriminating experiment

Replay identical arrivals with two or more TTFT/TPOT classes, then change their proportions midway through the trace. Hold model, output-length distribution, hardware, and offered rate constant. Compare current scheduling, fixed chunk budgets, and the proposed state-aware or credit-based selection. Add an experiment where length estimates systematically underpredict long outputs.

Count goodput as completed requests meeting both declared objectives per second, with rejection, timeout, and cancellation visible for all arrivals. Also report per-class attainment, worst-class queue delay, p99 inter-token gaps, preemption, memory occupancy, and scheduler overhead. A higher admitted-only success rate is not evidence of higher service capacity. Use execution traces to verify that gains arise from changed batch work rather than shorter outputs or dropped requests.

The useful next step is to check whether engine metadata can express the intended SLO and cadence end to end. Reuse available scheduling hooks, then measure the policy; neither a new priority field nor a paper's aggregate speedup establishes that integration.

## Sources

Checked 2026-10-14.

- [SCORPIO, arXiv 2505.23022v2, 2026-08-26](https://arxiv.org/html/2505.23022v2): token requirement proportions, virtual batch size, and admission/queue/batch coordination.
- [SOLA, MLSys 2025, §§4–5](https://proceedings.mlsys.org/paper_files/paper/2025/file/bc82dbfbfa43232be85b8d9838f49c3e-Paper-Conference.pdf): constrained workload control and state-aware ordering.
- [Andes, arXiv 2404.16283v1](https://arxiv.org/html/2404.16283v1): delivery-curve QoE and preemption-aware selection.
- [vLLM scheduler, commit 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/scheduler.py): current eligibility, budget, and priority mechanisms.
