<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# KV Quantization and Storage Codecs

English | [简体中文](quantization-storage-codecs_zh.md)

“Compressed KV” can mean lower-precision resident tensors or an encoded storage object that expands before attention. The former can reduce runtime memory and reads; the latter primarily reduces storage and transfer bytes. Confusing them produces incorrect capacity and performance predictions.

## Different representations, different costs

[KIVI, February 2024](https://arxiv.org/html/2402.02750v1) uses asymmetric quantization: keys per channel across tokens, values per token across channels. Persistent key-channel outliers and token-dependent value ranges motivate different axes. For each group, reconstruct `x_hat = s q + z`, where `z = min(x)` and `s = (max(x) - min(x))/(2^B - 1)`. The quantized integers, scales and offsets all consume memory.

Keys need enough arriving tokens to form a group. KIVI retains a recent full-precision residual window, quantizes older states and combines the two portions during attention. Its examples use group size 32 and residual length 128. A 2-bit payload is nominally one eighth of BF16, but metadata, residuals, padding and workspace reduce the actual memory saving. Tiny histories may obtain little benefit. The method's key/value asymmetry and residual window matter; “change dtype to two bits” is not the algorithm.

[CacheGen, October 2023](https://arxiv.org/html/2310.07240v1) instead creates bitstreams for cached contexts. Ten-token chunks use anchor tokens and quantized deltas, with layer-dependent precision followed by arithmetic coding. Multiple stored compression levels allow a controller to choose a representation, or raw-text recomputation, according to loading cost. The runtime decodes the bitstream back to KV tensors. Entropy coding is lossless relative to quantized symbols, not relative to the original floating-point cache.

For a storage codec, use `T_load = T_fetch(D_compressed) + T_decode + T_install`, allowing only measured overlap. Resident attention memory can remain close to the uncompressed size. For runtime quantization, measure `T_attention = T_read + T_dequant + T_compute`, including packing and scale access. A smaller representation can be slower when kernels are inefficient or the attention stage is not the service bottleneck.

## Current engines and source entry points

At the [2026-10-14 snapshot](README.md#evidence-snapshot), vLLM's [quantized-KV documentation](https://docs.vllm.ai/en/latest/features/quantization/quantized_kvcache/) describes FP8, calibrated scales, per-tensor/per-head choices and layer exclusions. Per-head support depends on the attention backend. These are existing mechanisms; they are not equivalent to KIVI's 2-bit representation. Defaults with unit scales and dataset-calibrated scales are separate quality conditions.

LMCache's [CacheGen guide](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/source/kv_cache_optimizations/compression/cachegen.rst) exposes `remote_serde: "cachegen"` and points away from deprecated in-process mode. Verify the matching MP setup and serializer path before an experiment. Mooncake transports registered bytes and Dynamo KVBM moves cache objects between tiers; neither establishes a model-specific low-bit attention representation merely by storing fewer wire bytes. vLLM's [NIXL compatibility rules](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/nixl_connector_compatibility.md) additionally constrain scale representation across endpoints.

## Quality and useful experiments

Locally, capture real K/V from the target model and separately sweep key axis, value axis, group size, residual window and scale calibration. Compare reconstructed tensors, attention outputs and final next-token distributions. This tests whether a failure comes from outlier handling, stale calibration or accumulated model error. Random Gaussian tensors cannot reproduce model outliers.

For a codec, hold its decoded dtype constant while varying encoded size and transfer bandwidth. If TTFT improves but resident KV bytes do not, the result is transport compression rather than runtime memory compression. For resident quantization, compare equal request counts and then equal memory budgets; the second comparison reveals capacity gains that a one-request test misses.

Service validation needs retrieval, multi-hop reasoning, long generation, code and multilingual inputs, with per-case quality plus TTFT, TPOT, peak memory and completed throughput. Remaining research is model-specific calibration and representation/kernel interoperability, not simply enabling already-supported FP8. No Foretoken quality or performance result is claimed.

[KV cache](README.md)
