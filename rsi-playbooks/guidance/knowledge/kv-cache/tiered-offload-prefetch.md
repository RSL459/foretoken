<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Tiered Offload and Asynchronous Prefetch

English | [简体中文](tiered-offload-prefetch_zh.md)

A cache hit is useful only when its exposed loading cost is smaller than the computation it replaces. Host RAM, SSD and remote storage extend capacity, but a high hit rate can coexist with worse first-token latency when staging, queueing or transfer completion becomes the critical path.

## Mechanism and crossover

For ordinary dense attention, approximate KV bytes per rank as `D = 2 L N Hkv d b`, using layers `L`, tokens `N`, locally stored KV heads `Hkv`, head dimension `d`, and bytes per element `b`. Head replication, MLA and hybrid models require their actual cache shapes instead. For a 32-layer model, 8 KV heads, dimension 128, BF16 and 8,192 tokens, the unsharded KV is 1 GiB. At an illustrative effective 20 GiB/s, the payload alone takes 50 ms; lookup, page faults, packing and admission are additional.

A first-order comparison is

`T_hit = T_lookup + T_queue + T_stage + max(0, T_copy - T_overlap) + T_remaining`.

Compare it with prefill of the same tokens, not an isolated attention kernel. Effective bandwidth is measured under concurrent loading and decode, not copied from a link specification. `T_overlap` counts actual useful concurrent computation; asynchronous API submission does not establish overlap.

A layerwise pipeline retrieves layer 0, computes its remaining work while retrieving layer 1, then waits only when the next layer is not ready. In steady state its stage time approaches `max(T_layer_copy, T_layer_compute)`, with startup and drain costs. A whole-prefix load before execution has different overlap opportunities. CPU/SSD staging can introduce a third stage, and a saturated host-memory path can serialize apparently independent transfers.

Prefetch also changes lifetime. Locate objects, protect their storage from eviction, reserve destination buffers, submit reads, admit completed data, then release the appropriate locks. Reserving too far ahead consumes useful cache capacity before the data is needed. Cancellation must not make a destination reusable while a transfer still owns it; determine the adapter's actual completion semantics before changing that lifecycle.

## Existing implementations

At the [2026-10-14 snapshot](README.md#evidence-snapshot), LMCache already has multi-tier lookup and prefetch. Its [controller implementation](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/lmcache/v1/distributed/storage_controllers/prefetch_controller.py) and [design](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/distributed/storage_controllers/prefetch_controller.md) describe L1 locks, L2 lookup-and-lock tasks, policy planning, destination reservations and result admission. The implementation currently resolves placement to one L1 manager; it is not evidence for arbitrary multi-L1 placement.

Dynamo KVBM's [onboarding](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-engine/docs/onboarding.md) covers HBM, pinned DRAM, SSD and object storage, including SSD-to-host staging before remote transfer. Its [offload pipeline](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-engine/src/offload/pipeline.rs) separates policy, batching, preconditions and transfer. Mooncake supplies asynchronous registered-memory transfers; its presence does not establish an engine's layerwise prefetch schedule. vLLM connector integration must be traced through scheduler allocation and worker consumption.

## Conditions and discriminating experiments

This approach suits repeated expensive contexts when transfer bandwidth and memory capacity are available. Short prompts, low reuse, shared PCIe contention and memory-constrained hosts can reverse the result. Saving completed KV also spends bandwidth; include offload traffic and evictions, not just loads.

Locally, replay equal-sized cached tensors with synchronous loading, asynchronous submission without compute, and layerwise loading with representative compute. Sweep size, tier and prefetch distance. Capture submission, readiness, layer waits, queue residence, host RSS, pinned bytes and actual overlap. If only the third case improves, overlap—not an intrinsically faster copy—is the explanation. If hit latency rises with concurrency while payload bandwidth stays flat, queueing is a stronger hypothesis than insufficient raw bandwidth.

At service level, compare cold prefill, GPU hits and each lower-tier hit on identical repeated prompts, including short and long reuse intervals. Record TTFT percentiles, decode latency of unrelated requests, cache residency and bytes moved. Remaining research concerns adaptive prefetch distance and admission under contention.

[KV cache](README.md)
