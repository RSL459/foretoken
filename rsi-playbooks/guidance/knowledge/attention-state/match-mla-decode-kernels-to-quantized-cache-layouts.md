<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Match MLA decode kernels to quantized cache layouts

English | [简体中文](match-mla-decode-kernels-to-quantized-cache-layouts_zh.md)

## Problem and upstream position

Multi-head Latent Attention (MLA) compresses token history into latent vectors shared by query heads. This reduces cache storage, but decode still reads that history, computes per-head scores, and reduces partial outputs. A small cache representation is not automatically a fast execution path: scale loads, irregular gathers, dequantization, and output projection can become dominant.

FlashMLA already implements dense and sparse MLA kernels. Its September 30, 2026 release is a significant compatibility boundary: the current README removes Hopper and DeepSeek V3/V3.2/V4.0 support and changes the cache formats for V4.1. Older models are directed to a fixed earlier commit, so select the implementation by model and cache format.

## What is actually stored and computed

A simplified MLA token has compressed latent state `c_t` and a positional key `r_t`. After absorbing projection matrices and the attention scale into the query, one query head scores a historical token as:

```text
score(t) = q_latent · c_t + q_position · r_t
z        = sum_t softmax(score(t)) * c_t
output   = project(z)
```

The shared latent is not a separate expanded K/V pair for every head. Absorption saves cache bytes while changing the dimensions and arithmetic the attention kernel sees. Model-specific projections and positional rules must remain intact.

At FlashMLA's pinned pre-breaking-change revision, the V3.2 sparse FP8 format stores one token in 656 bytes: 512 E4M3 latent bytes, four FP32 scales occupying 16 bytes, and 64 BF16 RoPE values occupying 128 bytes. Each scale covers 128 latent values. This is not a generic 656-byte MLA contract: it is one model's physical representation.

The current V4.1 format is different: its 512 FP8 values include the 64 RoPE dimensions, and sixteen E8M0 scales bring the total to 528 bytes. Its FP4 extra-cache representation packs 512 E2M1 values into 256 bytes plus 32 E4M3 scales, totaling 288 bytes; it is supported only as `extra_k_cache` alongside the V4.1 FP8 main cache. Feeding one layout to a kernel expecting another changes interpreted values, not merely speed. The earlier V4.0 format also differs in both dimensionality and where page scale rows live.

Paged sparse decode receives selected physical token locations. For example, selecting positions from several distant pages can require many scattered loads even though the selected-token count is small. Parallel split attention computes independently normalized partial results; combining them requires log-sum-exp statistics, not an unweighted average of outputs. Scheduling metadata describes how that work is partitioned and must match the current decode configuration.

## Conditions and trade-offs

The earlier sparse path covers SM90/SM100 and V3.2/V4.0 MQA layouts. The current repository documents V4.1 on SM100/SM103 and Ascend 950, with different software requirements and quantized-only decode. These source-level scopes do not establish complete engine, model, or graph-capture support on every listed platform.

FP8 cache can reduce traffic and increase request capacity, but scales, unpacking, and retained high-precision components reduce the ideal byte saving. FP4 may further change precision and kernel eligibility. Sparse attention changes which tokens are read; cache quantization changes their values. Compare these effects separately. Small batches can be launch-bound, while long-context, high-concurrency decode may be bandwidth-bound.

## Implementation and remaining design space

Start with the model-matched FlashMLA README and API, not the branch name. Inspect `get_mla_metadata`, `flash_mla_with_kvcache`, selected indices, and the engine's cache producer. Check whether metadata remains valid after sequence-length, top-k, query-count, or head configuration changes.

Remaining questions include layout-aware gather ordering, scale reuse, split selection for unequal lengths, and cache insertion/dequantization fusion. Reordering sparse reads must preserve the association between indices, values, and positional features. A hardware adapter may need a different tile schedule without changing the model's cache semantics. When sparse selection itself dominates, consult [sparse indexer routing](reduce-indexer-cost-with-query-dependent-head-routing.md) instead of tuning the MLA consumer alone.

## Discriminating experiments

Construct cache rows with independently recognizable latent, scale, and positional values before performance comparisons; a transposed or misplaced scale can produce plausible but wrong outputs. Compare quantized against high-precision cache at the same selected indices, then compare sparse against dense separately.

Sweep context length, batch, selected-token count, page locality, and decode query count, including speculative multi-token queries. Record actual bytes, effective bandwidth, scale/dequantization cost, partial-reduction cost, and metadata preparation. Then run the complete model with cache insertion and projection included. Service comparisons should report TPOT tails and successful throughput under equal memory budgets, plus a separate equal-concurrency comparison so capacity gains are not confused with faster per-request execution. Long-context quality checks must include retrieval and positional sensitivity.

## References

- [FlashMLA current README](https://github.com/deepseek-ai/FlashMLA/blob/2e5429fc5653bab6e081f09477126f731882a6a9/README.md): V4.1 formats, hardware scope, API, and September 30 breaking change.
- [Explicit earlier revision `ba89a3466e9470ad08ab39738d4e7bb66989e1e7`](https://github.com/deepseek-ai/FlashMLA/blob/ba89a3466e9470ad08ab39738d4e7bb66989e1e7/README.md): V3.2/V4.0 layouts and earlier dense/sparse decode contracts.
- [DeepSeek-V3.2 report, v1](https://arxiv.org/html/2512.02556v1): DSA's use of MLA MQA and model-level sparse selection.
