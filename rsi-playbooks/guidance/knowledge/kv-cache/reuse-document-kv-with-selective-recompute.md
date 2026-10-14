<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reuse Non-Prefix Document KV Through Selective Recomputation

English | [简体中文](reuse-document-kv-with-selective-recompute_zh.md)

Reusing a document's KV after inserting different preceding documents is not ordinary prefix caching. Even identical document tokens have changed causal context. CacheBlend addresses this by reusing most entries while recomputing selected tokens; relocation and semantic correction are separate operations.

## What must be repaired

Suppose cached document `B` was processed alone, but a new prompt is `A | B | question`. At layer 0, input embeddings for B can be unchanged apart from positions. At higher layers, B's hidden states should also depend on A. Rotating cached keys to their new positions repairs the positional convention, not that missing dependency.

For a RoPE key `k_p = R(p) k`, shifting by `delta` gives `R(delta) k_p = R(p + delta) k`, under the applicable RoPE convention. Values generally do not receive this rotation. Scaling variants, partial rotary dimensions and MLA require explicit geometry; applying a generic rotation to every cache channel is incorrect.

The [CacheBlend method, May 2024](https://arxiv.org/html/2405.16444v1) loads a layer's cached KV, recomputes Q/K/V for selected tokens, replaces their cached entries, and lets selected queries attend to the full causal KV. Their updated hidden states continue through later layers. Unselected entries retain the approximation from the original context. Selection therefore limits both computation and how much cross-document interaction is repaired.

A useful example is an instruction in A that changes how a sentence in B should be interpreted. Recomputing only the final question may repair question-to-document attention while leaving B's contextual representations stale. Recomputing some B tokens propagates additional information, but does not necessarily reproduce full prefill. Inter-document reasoning and conflicting instructions make stronger diagnostics than copying a fact from one unchanged document.

## Current implementation

In the [cited implementations](README.md#references), LMCache includes both older in-process blending and a multiprocess blend path. The [in-process blender](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/lmcache/v1/compute/blend/blender.py) selects tokens on configured check layers using squared L2 key differences in float32, takes a ratio-based top-k, restores sequence order and updates selected K/V.

The [MP module design](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/multiprocess/modules/blend.md) describes fingerprint matching, prefix plus non-prefix segments, sparse prefetch, K-only re-RoPE and token scatter into paged KV. All relevant rank/read-group objects must be available. Source modules include `lookup.py`, `retrieve.py` and `rope.py`. Matching and safe retrieval are not the same responsibility as the engine's selective recomputation.

The [current legacy guide](https://docs.lmcache.ai/kv_cache_optimizations/blending.html) labels in-process mode deprecated and recommends MP mode. Its example uses separately tokenized chunks and a separator; concatenating strings can change boundary tokens. Mooncake's byte transfer, Dynamo's tier onboarding and vLLM's ordinary prefix reuse do not, by themselves, repair non-prefix causal dependencies.

## Experiments and remaining questions

Use cached `A`, `B` and `C` separately, then test their permutations, a new system instruction, duplicated chunks, and partially allocated final blocks. For each resulting prompt, hold token IDs, positions and model weights fixed across the comparison methods. Compare full prefill, retrieval without recomputation, positional correction only, and several recompute ratios/check layers. Inspect per-layer K deviation and final next-token distributions. This separates positional failure from context-dependent error and inadequate token selection.

Then evaluate multi-hop document questions, contradictory evidence, summarization and multilingual boundary cases. Record quality by case, not only an aggregate average, together with TTFT, recomputed tokens, bytes fetched and failure-driven full recomputation. Profile retrieval separately from selection and model execution.

Open research includes selection stability across models, dependency repair under document reorder, and the quality/cost frontier of recomputation.

[KV cache](README.md)
