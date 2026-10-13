<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Model Loading and Storage

English | [简体中文](README_zh.md)

- Why is startup slow after the model is already downloaded? [Weight-loading pipelines and rank-local checkpoints](weight-loading-pipeline.md) separates I/O, tensor installation, transformations and first-request readiness.
- When should lazy mmap, eager reads, pinned buffers or parallel I/O be used? [Mmap, pinned memory and parallel I/O](mmap-pinned-parallel-io.md) explains page faults, staging lifetimes and bounded pipeline capacity.
- Can a warm worker or shared store accelerate another worker's loading? [Distributed weight storage and peer loading](distributed-weight-storage.md) examines current ModelExpress, Mooncake and Dynamo artifact paths and their compatibility boundaries.
- What survives sleep, restart or a cold restore? [Cold, warm and sleep/wake recovery](sleep-wake-recovery.md) separates host backups, IPC ownership, raw allocation artifacts and token replay.

These entries concern loading and storage mechanisms. Replica placement, scale-to-zero decisions and request routing belong to serving guidance; allocator and graph internals belong to runtime guidance.

## Evidence snapshot

Checked 2026-10-14.

- [LMCache, Mooncake, vLLM and Dynamo revisions](../kv-cache/README.md#evidence-snapshot): loading, storage and recovery implementation sources.
- [ModelExpress `main`](https://github.com/ai-dynamo/modelexpress/tree/db0cbce97184d9135d35c7290711f3053b220b6a), committed 2026-10-13 UTC: the upstream-integrated vLLM loader and loading strategy chain.

[Inference knowledge](../README.md) · [KV cache](../kv-cache/README.md)
