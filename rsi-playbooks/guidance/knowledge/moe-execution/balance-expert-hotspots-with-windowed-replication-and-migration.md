<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Balance expert hotspots with windowed replication and migration

English | [简体中文](balance-expert-hotspots-with-windowed-replication-and-migration_zh.md)

## Problem and current boundary

Expert parallelism finishes a layer when its slowest participating rank finishes. Equal numbers of stored experts do not imply equal work: routing preferences depend on layer, language, task, and current request mix. Replicating a hot logical expert across physical slots can spread execution without changing which function the model selects.

vLLM already implements windowed expert-parallel load balancing (EPLB), redundant experts, asynchronous weight transfer, preservation of existing intra-GPU slots, and an optional conflict-free migration schedule. Treat these as the starting point. The remaining question is when rebalancing pays for its observation lag, transfer traffic, and extra memory under a changing service workload.

## Execution sequence

The engine collects expert-load statistics from forward execution and forms a history window. At the configured interval, the policy consumes global load estimates and the previous physical-to-logical mapping.

The default policy first packs logical expert groups across nodes when model grouping permits a hierarchy. It then assigns redundant slots to experts with high estimated load per replica and packs physical experts across GPUs. In the replication loop, an expert with load `w_e` and `r_e` copies has estimated per-copy load `w_e/r_e`. Increasing `r_e` lowers that estimate, but equal splitting is a planning assumption, not a measurement of the subsequent batch.

For example, estimated loads `[100,20,20,20]` and one extra slot suggest replicating the first expert, whose estimated per-copy load becomes 50. This is an illustrative allocation, not a claim that GEMM time falls by half. Tensor shapes and communication still determine actual runtime.

The policy preserves existing slots where possible. The async worker snapshots placement, computes the new mapping, transfers one layer's required weights into staging storage, waits for writes to finish, and publishes a pending result. The forward-side consumer must install weights and consume that result before the staging buffer is reused. Mapping and weights must become usable together; publishing only the new IDs would select the wrong parameters.

The cited migration scheduler coalesces transfers for a directed rank pair and groups disjoint endpoint pairs. A rank communicates with at most one peer in each batch. Transfers remaining on the same GPU need no remote copy.

## Conditions and trade-offs

Windowed balancing suits persistent skew better than rapidly rotating hotspots. Short windows respond quickly but can chase sampling noise; long windows can preserve yesterday's placement after a workload transition. Step intervals are engine-step counts, so their wall-clock meaning changes with load.

Redundant expert weights and quantization scales consume memory that could otherwise hold KV cache. Migration consumes network and device bandwidth even when asynchronous. A non-blocking host call does not imply interference-free inference. Quantized weight layouts and their scales must migrate as one expert representation, and captured execution must retain valid storage and mappings.

## Experiments that distinguish explanations

Use three routing regimes: a stable hotspot, an abrupt domain change, and hotspots alternating faster than the observation window. Record per-layer logical load, physical load, maximum rank duration, replica occupancy, transferred bytes, migration intervals, KV capacity, and client latency. Keep the redundancy budget fixed while comparing windows and intervals.

If physical imbalance falls but TPOT rises during migration, investigate transfer interference rather than concluding balancing failed mathematically. If placement follows a hotspot only after it disappears, observation delay is the cause. If equal token counts still produce unequal GEMM durations, token count is an insufficient cost model.

Run full-service traffic long enough to include multiple rebalance cycles, not only a post-rebalance steady state. Check outputs across mapping changes and evaluate answer quality with the unchanged logical router. Report ordinary periods and migration periods separately, alongside overall TTFT/TPOT and success counts.

## References

vLLM commit [6849ca69](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9), specifically [default policy](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/eplb/policy/default.py), [async worker](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/eplb/async_worker.py), and `migration_scheduler.py`; also the [official EP deployment guide](https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/). The open design space is workload-aware timing and measured execution-cost estimation. For per-batch fluctuations, see [online replica assignment](balance-batch-load-through-expert-replica-assignment.md).
