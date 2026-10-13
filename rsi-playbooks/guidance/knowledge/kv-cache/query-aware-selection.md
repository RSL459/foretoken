<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Query-Aware Selection and Eviction

English | [简体中文](query-aware-selection_zh.md)

Reducing KV reads is different from reducing stored KV. A selector can retain all information and choose different pages for each query; an eviction method permanently removes entries from the active cache. The distinction determines whether a later question can recover information missed by an earlier one.

## Quest's page-level mechanism

[Quest, June 2024](https://arxiv.org/html/2406.10774v1) keeps the complete cache and adds minimum and maximum key values per dimension for each page. Given query `q`, page `p` receives the score bound

`U_p(q) = sum_i max(q_i min_p(k_i), q_i max_p(k_i))`.

For any key in that page, its dot product with q cannot exceed this coordinate-wise bound. The extreme values may belong to different tokens, so the bound can be loose. Ranking bounds is not an exact top-token search and does not certify that omitted probability mass is small.

Execution reads page metadata, scores pages, selects a budgeted top-k, and reads K/V only from selected pages for the actual attention calculation. For positive `q_i`, the maximum key component is relevant; for negative `q_i`, the minimum is relevant. A page with a newly useful negative-direction key can therefore be selected even if it was irrelevant to the preceding query.

If page size is `S`, context length `N`, and selected-page count `K`, approximate metadata-plus-KV traffic relative to a full K/V scan is `1/S + KS/N`, assuming equal element widths and ignoring selection/workspace traffic. For `S=16`, `N=32768` and `K=128`, this is about 12.5%, not a prediction of 8× service speedup. Scoring, top-k, launch costs and non-attention layers remain. Quest keeps its first two layers dense in the reported configuration because useful sparsity is weaker there.

By contrast, historical-attention eviction can discard an entry because it has not recently received attention. If the next query asks about that entry, it is unavailable unless a separate backing store reloads it. Static sink/recent-window retention protects particular token classes, not arbitrary later retrieval. None of these methods should be described as equivalent compression.

## Applicability and current-state boundaries

Quest's original method evaluates long-context decoder models and dedicated page-selection kernels. Its accuracy depends on the model, layer, token budget and task; multi-fact aggregation can require more pages than a single passkey. Keeping all KV means HBM capacity is not inherently reduced. Moving unselected pages to another tier adds a different fetch-and-read scheduling problem.

The [2026-10-14 upstream snapshot](README.md#evidence-snapshot) establishes existing infrastructure, not universal deployment of Quest. vLLM's [NIXL compatibility document](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/nixl_connector_compatibility.md) describes paged cache geometry. LMCache's [MP blend retrieval](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/multiprocess/modules/blend.md) supplies sparse segment retrieval. Dynamo [KVBM onboarding](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-engine/docs/onboarding.md) and Mooncake's [Transfer Engine](https://github.com/kvcache-ai/Mooncake/blob/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3/mooncake-transfer-engine/include/transfer_engine.h) move stored data. These mechanisms do not establish query-dependent page scoring. Whether a target backend already provides an equivalent selector must be checked in that backend before proposing an implementation.

## Experiments that separate selection from deletion

Capture real queries and full KV over a long generation. Compare full attention, Quest-style bounds, exact page ranking from full attention, and historical eviction at the same token budget. Exact ranking is a diagnostic upper reference, not a practical free operation. Inspect selected-page recall, omitted attention mass, output deviation, metadata bytes, selection time and KV-read time.

Construct two consecutive questions about different early passages. A retained-cache selector can choose a previously unused page on the second query; eviction cannot without reload. Add dispersed multi-fact aggregation, distractor-rich pages and position sweeps. These distinguish recoverability, loose page bounds and insufficient budgets.

At service level, compare quality and completed throughput across context lengths and concurrency, measuring peak memory separately from traffic. The attention owner handles selection kernels; cache research concerns metadata residency, backing-store fetches and quality-aware budgets. Remaining questions include metadata under quantization, page-size trade-offs and dynamic budgets. No Foretoken implementation or speedup is asserted.

[KV cache](README.md)
