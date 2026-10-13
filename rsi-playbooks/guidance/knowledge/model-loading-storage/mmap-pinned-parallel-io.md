<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Mmap, Pinned Memory and Parallel I/O

English | [简体中文](mmap-pinned-parallel-io_zh.md)

Lazy mapping, eager reads and pinned staging solve different problems. Mmap avoids an initial full-file copy but can trigger many small page faults. Eager loading changes the access pattern and memory footprint. Pinned host buffers enable asynchronous device transfers but neither make the filesystem faster nor guarantee overlap.

## Where bytes actually move

A lazy safetensors reader maps file-backed pages and touches tensor ranges as weights are requested. On a warm local filesystem, those pages may already be in RAM. On network storage, irregular tensor access can turn into expensive faults and small reads. The tensor-to-device copy still has to happen; mmap is not a direct storage-to-GPU transfer.

An eager reader loads a whole shard before yielding tensors. This makes file access more sequential, while materializing a larger CPU state dictionary. Parallel shard reads can increase outstanding I/O and also multiply resident host memory. Eight threads do not imply eight times bandwidth, especially when ranks compete for one disk or network mount.

Pinned staging introduces reusable host buffers: read a chunk, place it in pinned memory, enqueue H2D, and return the buffer to the pool only after its copy completes. The pinned-memory capacity is approximately `number_of_buffers × buffer_size`. A pipeline transferring at B bytes/s with stage latency t needs roughly `B × t` bytes in flight to avoid starvation; this is a sizing estimate, not a universal buffer default. Too much pinned memory reduces reclaimable RAM and can harm co-located workloads.

For example, a fast disk feeding pageable CPU tensors may stall H2D preparation; adding storage-reader threads will not remove that copy/staging cost. Conversely, pinned buffers cannot rescue a saturated remote filesystem. A direct GPU storage path removes some host staging only when the filesystem, driver and loader actually support it.

## Current vLLM behavior

The [2026-10-14 inspected weight utilities](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/weight_utils.py) implement lazy, eager and prefetch safetensors strategies. Prefetch populates the page cache; it is not pinned GPU staging. Automatic prefetch recognizes specific network filesystems and considers available RAM. Multithreaded loading uses a separate iterator, and [DefaultModelLoader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/default_loader.py) rejects combining that path with non-default safetensors strategies.

The same utilities expose fastsafetensors and instanttensor iterators. The instanttensor path uses owned copies because a yielded tensor must remain valid after reusable loader storage changes. The fastsafetensors path can use GDS and has a no-GDS alternative. These are already integrated options, not future ports.

The [RunAI loader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/runai_streamer_loader.py) forwards concurrency and memory-limit settings to its external streamer. Do not describe this thin adapter as implementing its own I/O thread pool. [ServerlessLLM's method](https://arxiv.org/html/2401.14351v1) provides the original aligned-chunk, pinned-pool and multi-tier pipeline rationale. Dynamo KVBM and LMCache's pinned cache tiers are relevant memory competitors, not weight-loading substitutes; Mooncake registration also adds host-memory lifetime constraints.

## Experiments that locate the bottleneck

Use the same checkpoint on local and network storage. Compare cold and warm cache, lazy/eager/prefetch, and supported threaded versus specialized loaders. Record actual storage bytes, major/minor faults, host RSS, pinned bytes, H2D occupancy, per-rank load time and aggregate storage throughput. If eager helps only cold network reads, access pattern is implicated. If warm loading remains slow with little I/O, inspect installation and transfer stages.

Separately sweep buffer size and in-flight count in an existing loader that exposes those choices; do not invent unsupported flags. Require completion-ordered buffer reuse and verify model outputs. Increased concurrency that raises RSS without throughput indicates excess buffering rather than progress.

At service level, start multiple workers together and measure readiness, first-request latency and impact on an already-serving worker. Remaining work concerns bounded buffering and storage/host/device overlap under shared pressure. It is not adding unconditional prefetch or maximum reader threads. These are proposed measurements, not Foretoken results.

[Model loading and storage](README.md)
