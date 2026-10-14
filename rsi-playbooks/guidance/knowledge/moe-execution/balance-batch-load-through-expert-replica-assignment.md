<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Balance batch load through expert replica assignment

English | [简体中文](balance-batch-load-through-expert-replica-assignment_zh.md)

## Problem and current boundary

A placement balanced over a long history can still produce a slow current batch. Small batches fluctuate, and splitting a logical expert's tokens equally between replicas need not equalize total work across their host GPUs. The placement decision and the per-batch assignment decision therefore operate at different timescales.

DeepSeek's LPLB implements the second decision: count current logical expert assignments, solve a constrained load redistribution problem, and redirect them to physical experts. Its README describes an early research implementation, primarily motivated by training fluctuations, with performance still under evaluation. This is usable algorithm and source evidence, not proof that a per-batch solver improves decode serving.

## Execution mechanism

First construct a redundancy topology: an expert stored on one GPU also occupies a redundant slot on another. LPLB's cited `Planner` requires a structured mapping with equal redundant-slot counts and exactly two physical copies for replicated logical experts. History-based EPLB reorders originals; the hottest candidates on each device are selected for this topology.

For every batch, `count_workload` counts selected logical expert IDs. `solve_probs` synchronizes counts through the configured group unless its DeepEP communication path is initialized, then invokes the compiled solver. `weighted_select_target` maps the original IDs to physical slots using the resulting distribution ratios and per-SM count metadata. Only the physical destination changes; the chosen logical expert and router weight must remain unchanged.

An explanatory minimax formulation is:

```text
minimize z
subject to sum_r x[e,r] = n_e
           sum_e x[e,r] <= z
           x[e,r] >= 0, only where replica(e,r) exists
```

Here `e` indexes logical experts, `r` indexes destination GPU ranks, `n_e` is current logical demand, `x[e,r]` is demand assigned to a copy on rank `r`, and `z` bounds each rank's total assigned rows. This token-count model assumes comparable cost per expert row. Finite row counts require an integer realization after fractional planning; the source's mapping kernel implements that stage.

Suppose rank A has 80 token-expert rows and B has 20; 40 of A's rows belong to an expert replicated on B. Moving 30 of those rows gives totals 50 and 50. Moving rows for an unreplicated expert is not permitted. With a top-k router these are expert evaluations, not independent request counts.

## Conditions and trade-offs

Planning counts is cheaper than loading new weights every batch, but it only moves work along the existing replica graph. More topology edges consume more expert storage. LPLB's restriction to two copies limits how it handles one overwhelmingly hot expert relative to unrestricted multi-copy placement.

The upstream README reports approximately 100 microseconds for an intra-node solve, with larger inter-node cost; that is a source-reported estimate, not a current-device measurement. A solver on the critical path can cost more than it saves for single-request decode. The implementation also explicitly balances total token counts rather than nonlinear grouped-GEMM execution times.

The cited planner references the older DeepEP `Buffer` API and NVSHMEM-based synchronization. Current DeepEP main uses the V2.5 `EPBuffer` API and removed NVSHMEM. These versions do not establish drop-in compatibility. Reuse the algorithm or adapt its owned communication boundary; do not silently combine current dependencies with old integration assumptions.

## Experiments and service validation

Replay real router IDs, then hold mean expert demand constant while varying batch-to-batch variance. Compare fixed assignment, equal replica splitting, and LPLB at identical placement and memory budgets. Measure histogram creation, workload exchange, solver, ID mapping, dispatch, GEMM, and combine separately; also time the full layer.

If maximum token load falls but layer time does not, distinguish solver overhead, topology traffic, and small-GEMM nonlinearities. Include a stable single hotspot to expose the two-copy limit, and tiny batches to locate the planner's break-even region. Inspect feasibility outcomes rather than treating every solver invocation as a successful optimization.

Before serving, check physical IDs resolve to byte-equivalent expert representations, including scales. Evaluate the complete model with unchanged routing, then run concurrency-one and burst workloads. Observe client TPOT, success, output lengths, and quality; include planning overhead in every service result.

## References

[LPLB README and planner](https://github.com/deepseek-ai/LPLB/tree/0490f79452f7ef277e814449600b1b1dd4c663b3), commit `0490f794`, including `lplb/planner.py` and `lplb/eplb.py`; [current DeepEP](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509). Current gaps are engine integration, version-compatible workload exchange, and a measured latency break-even. See [windowed rebalancing](balance-expert-hotspots-with-windowed-replication-and-migration.md) for the slower placement loop.
