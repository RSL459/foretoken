<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Diagnose KV handoff stalls through fan-in transfer profiling

English | [简体中文](diagnose-kv-handoff-stalls-through-fan-in-transfer-profiling_zh.md)

## Problem and mechanism

A fast NIC does not guarantee fast P/D handoff. KV movement includes finding the source, registering or staging memory, building descriptors, transferring shards, converting layouts where required, and making completion visible before decode reads the cache. Several producers can saturate one consumer or share a link with expert traffic.

For ordinary full-attention GQA, logical cache bytes for S tokens are approximately `K = 2*S*L*H_KV*d*b`, where L is layer count, H_KV the number of KV heads, d head dimension, and b bytes per element. The factor two covers keys and values. This excludes allocator padding, scale metadata, replication and transfer framing; MLA, sliding-window and hybrid-state models require their actual representation instead.

An arithmetic example with S=32768, L=32, H_KV=8, d=128 and BF16 b=2 gives 4 GiB. An ideal 50 GB/s effective path already needs about 86 ms. At 10 such requests/s, payload demand is approximately 43 GB/s, leaving little headroom. FP8 KV roughly halves element bytes, but scales, conversion and model quality still matter. FP8 weights alone change none of this calculation.

A useful latency decomposition is `T_X = Q_X + setup + pack + K/B_effective + unpack + completion`. Effective bandwidth depends on message size and competing flows, not the link's line rate. Chunking and layerwise overlap can reduce exposed transfer time while extending buffer lifetimes. Starting D before usable shards are available merely converts transfer delay into decode stalls.

## Hardware and lifetime costs

Keep GPU/NIC affinity, NUMA, PCIe and rail count explicit. Device-to-device RDMA differs from TCP staging through pinned host memory; the latter adds GPU↔host copies, memory-bandwidth contention and extra buffers. A node-local NVLink path is different again. More transfer concurrency can improve utilization until it increases queueing or stalls compute.

The producer retains source pages until transport completion confirms that they will no longer be read; the consumer retains its destination pages for decode. A failed or canceled transfer must be quiesced before either buffer is reused. Cross-TP layouts may need reshaping or replicated sends; topology-compatible placement can save more than a faster transport backend. Do not silently assume a connector supports arbitrary TP, KV dtype or model-state combinations.

## Public evidence and integration

[NIXLBench's README](https://github.com/ai-dynamo/nixl/blob/01656768741dc87922a2045feff72921e193d981/benchmark/nixlbench/README.md) at `01656768` (2026-10-13) exposes pairwise, many-to-one and one-to-many patterns, DRAM/VRAM segments, backend selection and latency percentiles. It is a transfer measurement tool, not proof of service-level overlap.

The 2026 [AFD design-space paper](https://arxiv.org/html/2605.28302v1) explicitly models congestion and compute/communication overlap with AstraSim. Its 450-versus-25 GB/s placement comparison is a modeled NVLink/InfiniBand contrast, not a portable measured KV speedup. [MegaScale-Infer](https://arxiv.org/html/2504.02263) measures BF16 MoE M2N communication and explains completion, CPU proxy, small-message and traffic effects. That per-layer activation traffic is not the same payload as one-time P/D KV transfer.

Foretoken's [E/P/D deployment guide](../../../../examples/encoder-prefill-decode/README.md) states Mooncake RDMA by default and host-staged TCP as an alternative, while encoder state uses shared storage in that example. Its [workflow](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs) retains cross-stage cleanup.

## Experiments and remaining questions

First generate messages from the model's true cache layout. Measure setup separately from steady-state transfer; sweep size, shard count and fan-in. Include a compute kernel concurrently, then add competing EP traffic. Capture p50/p99 latency, useful bytes/s, host copy time, pinned-memory pressure and registration reuse. A pairwise peak alone cannot explain a many-to-one service stall.

Then replay equal P/D traffic with node-local, cross-node RDMA and TCP paths where supported. Keep model, weight/KV dtype, TP layout and cache-hit distribution fixed. Correlate transfer-completion events with client TTFT; measure stalled D time and source-page retention. Include cancellation and a missing peer to check eventual cleanup without interpreting failed requests as faster completion. Open questions include congestion-aware pair selection, size-aware transfer admission and joint scheduling of KV and expert traffic. Network mechanisms beyond this boundary are in [parallelism and communication](../parallelism-communication/README.md).

[Back to disaggregated serving](README.md)
