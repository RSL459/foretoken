<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# KV Cache

English | [简体中文](README_zh.md)

Cache contents, residency and movement determine reuse cost and capacity. Request routing and prefill/decode placement belong to serving guidance; attention execution belongs to attention guidance.

- Does loading saved KV actually beat recomputing it? [Hide KV Loading Latency Through Tiered Prefetch](hide-kv-loading-latency-through-tiered-prefetch.md) models the exposed transfer cost, staging capacity and reuse lifetime.
- Can cached documents be reused after their order or preceding context changes? [Reuse Non-Prefix Document KV Through Selective Recomputation](reuse-document-kv-with-selective-recompute.md) explains positional correction, selective recomputation and remaining semantic error.
- Which compression reduces runtime memory, and which only reduces storage or wire bytes? [Choose KV Quantization or Storage Codecs for Compression](choose-kv-quantization-or-storage-codecs-for-compression.md) separates KIVI, calibrated FP8 and CacheGen.
- Can fewer KV reads preserve answers without permanently deleting information? [Reduce KV Reads Through Query-Aware Page Selection](reduce-kv-reads-through-query-aware-page-selection.md) distinguishes Quest's page selection from irreversible cache eviction.
- Why is a fast network still slow or incompatible? [Reduce KV Transfer Overhead: Layouts, Registration, and Connectors](reduce-kv-transfer-overhead-layouts-registration-and-connectors.md) follows descriptors, geometry, completion and multi-connector ownership.

## References

- [LMCache `dev`](https://github.com/LMCache/LMCache/tree/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224): tiered storage, prefetch and blending.
- [Mooncake `main`](https://github.com/kvcache-ai/Mooncake/tree/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3): registered-memory transfers.
- [vLLM `main`](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9): quantized KV, transfer compatibility and connector composition.
- [Dynamo `main`](https://github.com/ai-dynamo/dynamo/tree/7708f041a965e35374af976ab8ad610b9537e3bc): KVBM onboarding, offload and physical transfer.

[Inference knowledge](../README.md) · [Model loading and storage](../model-loading-storage/README.md)
