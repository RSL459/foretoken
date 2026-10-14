<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Avoid KV Thrashing Through Memory-Aware Batch Selection

English | [简体中文](avoid-kv-thrashing-through-memory-aware-batch-selection_zh.md)

A request can fit when admitted and still exhaust KV capacity as its output grows. Repeatedly evicting and recomputing requests then converts useful inference into recovery work. The scheduling question is how to keep the running set feasible without reserving so much hypothetical future memory that the GPU becomes idle.

## Trace the existing failure path

The cited vLLM V1 scheduler calls `kv_cache_manager.allocate_slots` while building a schedule. If allocation fails, it chooses a running victim. Under priority scheduling, it selects the greatest `(priority, arrival_time)` pair; otherwise it selects the tail of the running list. Blocks must actually be freeable before preemption proceeds. In-flight execution and deferred frees matter: logically canceling work does not make every block immediately reusable.

`_preempt_request` releases KV and encoder state, resets computed-token progress, clears speculative tokens, marks the request preempted, and returns it to the waiting queue. If already selected work is removed from the current schedule, the appropriate budget is restored. Resuming requires rebuilding the missing state for the retained request history. Prefix caching may salvage reusable blocks, so reset progress should not be interpreted as a guarantee that every historical token is recomputed.

vLLM's current optimization guide recommends watching preemption counts and reducing concurrent pressure or supplying more KV space. It identifies recomputation as V1's default rather than presenting CPU swapping as the default remedy.

## Why admission-time fit is insufficient

Take two requests with 8K input tokens and an expected 1K-token output. Both may fit initially. If each instead generates 8K tokens, their combined KV footprint nearly doubles, apart from block rounding and sharing. A token-count approximation for an ordinary dense attention model is:

`KV_bytes ≈ resident_tokens × 2 × layers × KV_heads × head_dim × element_bytes`.

Use the engine's actual per-rank cache layout for decisions: tensor parallelism, MLA, hybrid models, shared prefixes, and allocation groups change this simple estimate. Already-computed prefix blocks and future output blocks also have different sharing opportunities.

SOLA's peak-memory prediction checks the effect of admitting a request on future memory consumption before executing it. Its scheduler explicitly excludes swapping and preemption from the simplified algorithm, preferring a feasible workload. SCORPIO combines output-length prediction with latency-aware admission, highlighting the same uncertainty: optimistic output predictions can overfill a future running set even when the present set fits.

There is a continuum between current-footprint admission and reserving the maximum possible output for every request. The former risks repeated recovery; the latter wastes memory when most outputs are short. The useful design variable is the cost of prediction error and how the engine changes selection when that error becomes observable, not simply whether a length predictor exists.

## Ownership and remaining design space

Only the engine can decide whether blocks are reclaimable, select a victim consistent with scheduling state, and resume execution correctly. Foretoken's request layer can avoid sending more work to a pressured instance using its observations and can enforce ingress concurrency. Lower ingress concurrency limits new work; existing KV is released by the engine as requests finish or are canceled. Cluster orchestration supplies replicas or a different parallelism layout on a slower timescale.

A candidate policy can consider estimated remaining output, saved computation, priority, and deadline slack when selecting the running set. The trade-off is explicit: evicting a large old request may recover substantial memory but destroy expensive progress; evicting short requests can harm many deadlines.

## Experiment that exposes thrashing

Keep prompt distribution constant and vary only output tails: mostly short responses, occasional long responses, and a correlated burst of long responses. Fix maximum output allowance, sampling, KV capacity, and offered load. Compare current selection with a memory-aware candidate and include an output predictor biased toward short responses.

Record original arrivals, completed requests satisfying TTFT and TPOT, preemptions per completion, recomputed tokens, GPU work spent on recovery, KV occupancy, and time to resume each victim. Collect p99 token gaps as well as average TPOT: a pause followed by fast generation can hide in the average. Track per-class completion so a policy cannot improve aggregate goodput merely by repeatedly displacing one tenant.

Revisit token budgets and active-sequence limits before changing recovery machinery. If reducing the running set removes preemption at similar goodput, that simpler control is a stronger candidate than a new eviction implementation.

## References

- [vLLM scheduler, commit 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/scheduler.py): `allocate_slots`, `_preempt_request`, victim selection, and deferred-free constraints.
- [vLLM optimization guide](https://docs.vllm.ai/en/latest/configuration/optimization/): preemption signals and current operational controls.
- [SOLA, MLSys 2025, §5.1](https://proceedings.mlsys.org/paper_files/paper/2025/file/bc82dbfbfa43232be85b8d9838f49c3e-Paper-Conference.pdf): future peak-memory checks at batch admission.
- [SCORPIO, arXiv 2505.23022v2, 2026-08-26](https://arxiv.org/html/2505.23022v2): prediction-dependent admission under heterogeneous objectives.
