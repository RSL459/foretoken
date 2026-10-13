<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# KV Cache

English | [简体中文](README_zh.md)

Choose an entry by the question being investigated. These notes cover cache contents, residency and movement; request routing and prefill/decode placement belong to serving guidance, while attention execution belongs to attention guidance.

- Does loading saved KV actually beat recomputing it? [Tiered offload and asynchronous prefetch](tiered-offload-prefetch.md) models the exposed transfer cost, staging capacity and reuse lifetime.
- Can cached documents be reused after their order or preceding context changes? [Non-prefix reuse and CacheBlend](non-prefix-cache-blending.md) explains positional correction, selective recomputation and remaining semantic error.
- Which compression reduces runtime memory, and which only reduces storage or wire bytes? [KV quantization and storage codecs](quantization-storage-codecs.md) separates KIVI, calibrated FP8 and CacheGen.
- Can fewer KV reads preserve answers without permanently deleting information? [Query-aware selection and eviction](query-aware-selection.md) distinguishes Quest's page selection from irreversible cache eviction.
- Why is a fast network still slow or incompatible? [Transfer layout, registration and connector composition](transfer-layout-registration.md) follows descriptors, geometry, completion and multi-connector ownership.

## Evidence snapshot

Checked 2026-10-14 against these upstream revisions, all committed on 2026-10-13 UTC:

- [LMCache `dev`](https://github.com/LMCache/LMCache/tree/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224): tiered storage, prefetch and blending.
- [Mooncake `main`](https://github.com/kvcache-ai/Mooncake/tree/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3): registered-memory transfers.
- [vLLM `main`](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9): quantized KV, transfer compatibility and connector composition.
- [Dynamo `main`](https://github.com/ai-dynamo/dynamo/tree/7708f041a965e35374af976ab8ad610b9537e3bc): KVBM onboarding, offload and physical transfer.

[Inference knowledge](../README.md) · [Model loading and storage](../model-loading-storage/README.md)
