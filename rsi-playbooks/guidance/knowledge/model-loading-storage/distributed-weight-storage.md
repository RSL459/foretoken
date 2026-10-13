<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Distributed Weight Storage and Peer Loading

English | [简体中文](distributed-weight-storage_zh.md)

A warm peer can supply installed weights, while a shared store can supply checkpoint files or prepared artifacts. These sources remove different startup work. A byte-compatible transfer must also preserve model identity, rank layout and runtime interpretation; reaching a peer is not enough.

## Follow the source representation

A file-cache hit still requires checkpoint parsing and parameter installation. A runtime-tensor peer can avoid repeated transformations if its tensor names, shapes, dtype, sharding and backend representation match the target. An allocation artifact instead supplies raw bytes and needs external knowledge to reconstruct tensor views. None of these automatically restores request KV or runtime execution state.

In an illustrative example, a rank needs 10 GiB of runtime weights. A peer delivering 40 GiB/s has a 250 ms payload floor, while a file source delivering 5 GiB/s has a 2 s floor. Metadata discovery, registration, source synchronization, installation and warmup are additional. Simultaneous targets divide source bandwidth and may compete with source inference. Peer loading is not a free acceleration merely because model files are absent from the path.

A valid pipeline discovers a compatible source, obtains its tensor manifest, allocates target storage, builds and executes transfers, checks completion, finalizes engine-specific state, then publishes the target as usable. If an attempt partially changes target tensors, retry must not mix two incompatible sources. The loader owns that recovery boundary, not an external benchmark client.

## Current upstream paths

[ModelExpress's inspected architecture](https://github.com/ai-dynamo/modelexpress/blob/db0cbce97184d9135d35c7290711f3053b220b6a/docs/ARCHITECTURE.md) and [vLLM loader](https://github.com/ai-dynamo/modelexpress/blob/db0cbce97184d9135d35c7290711f3053b220b6a/modelexpress_client/python/modelexpress/engines/vllm/loader.py) already implement a strategy chain: peer RDMA, eligible server cache, InstantTensor, ModelStreamer, GDS and engine-native loading. Source availability and configuration decide eligibility. Peer bytes use NIXL rather than passing through the central server. File-cache streaming reconstructs a local snapshot when shared storage is unavailable.

vLLM has a [native ModelExpress wrapper](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/modelexpress_loader.py). For actual fallback behavior and compatibility, continue into ModelExpress rather than inferring it from that adapter. The source/runtime identity and worker incarnation matter when selecting live tensor state.

Mooncake's [weight-management document](https://github.com/kvcache-ai/Mooncake/blob/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3/docs/source/design/mooncake-reshard/weight-management.md) distinguishes implemented publication/revision metadata, lease state and HA recovery from follow-up client/RPC surfaces and managed reader integration. Check the corresponding `weight_store_manager.cpp` and `weight_metadata_store.cpp` when continuing that work.

Dynamo's [weight artifact implementation](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/gpu_memory_service/v1/snapshot/weight_artifact.py) stores aligned allocation ranges and restores them into a fresh GMS server. It does not encode tensor names/shapes/dtypes. LMCache's KV persistence addresses a different object and cannot serve as a weight checkpoint. All revisions are identified in the [source snapshot](README.md#evidence-snapshot).

## Discriminating experiments

Locally compare native loading, a warm file cache, a compatible peer and a supported artifact restore. Fix the exact model revision, runtime dtype, transformations and rank geometry. Measure discovery, source readiness, registration, payload, finalization, storage traffic and source-worker latency. Inspect the chosen strategy: a successful run through native fallback does not validate the peer path.

Test one target and several simultaneous targets. If peer payload time rises with target count while file parsing disappears, source fan-out is the bottleneck. If transfer is fast but readiness unchanged, finalization or warmup dominates. Exercise source departure and a partial transfer to confirm the loader's real recovery behavior.

At service level, validate logits and generated outputs, readiness to first usable response, and impact on the serving source. The remaining space is compatible representation reuse, source fan-out and lifecycle integration.

[Model loading and storage](README.md)
