<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce indexer cost with query-dependent head routing

English | [简体中文](reduce-indexer-cost-with-query-dependent-head-routing_zh.md)

## Problem and upstream position

DeepSeek Sparse Attention (DSA) does not discover relevant history for free. A lightweight indexer first scans historical keys; only then does expensive MLA attend to selected tokens. Reducing the consumer to a fixed top-k can expose the indexer's linear decode cost and quadratic full-prefill work.

DSA is already implemented upstream. At the cited vLLM revision, the indexer includes fused query RoPE/quantization, compressed logits, multiple device backends, distributed exact top-k merging, and candidate-block masking for two-level selection. MISA, published in May 2026, explores a different selection axis: can query-dependent selection of indexer heads reduce scoring work without losing important tokens?

## Mechanism: selecting heads before selecting tokens

For query position `t`, historical position `s`, and indexer head `j`, let `q(t,j)` be the query, `k(s)` the shared index key, and `w(t,j)` the learned head weight. DSA's index score is:

```text
I(t,s) = sum_j w(t,j) * ReLU(q(t,j) · k(s))
selected(t) = topk_s I(t,s)
```

This is not the main MLA softmax. The learned indexer estimates which historical tokens deserve the more expensive attention computation. The DeepSeek report describes training the indexer against aggregated attention and then training with sparse selection, including 2,048 selected tokens per query. Arbitrarily replacing this selector changes learned model behavior.

MISA routes along the indexer-head axis. Partition the history into blocks, mean-pool each block's index keys, and evaluate a coarse affinity for every head. Select the most useful `h` heads for this query, scan every historical token using only those heads, and feed the resulting token top-k to unchanged sparse MLA. With `H` indexer heads, history length `L`, and pooling block size `B`, scoring work changes approximately from `H*L` to `H*ceil(L/B) + h*L` per query. It still reads historical index keys; fewer arithmetic operations do not guarantee lower memory traffic.

The paper's MISA† variant first selects a larger candidate set with routed heads, then reranks those candidates using all heads. Its example uses 8 routed heads, pooling blocks of 1,024 tokens, 8,192 candidates, and a final 2,048 tokens. If one relevant token lies outside the candidate set, reranking cannot recover it. Mean pooling may hide a rare high-affinity key; head selection therefore has no formal exact-top-k guarantee in the cited paper.

## Conditions and trade-offs

The paper evaluates pretrained DSA models, including DeepSeek-V3.2 and GLM-5, without retraining. This is not a drop-in transformation for arbitrary dense attention or GQA. The actual model's head count, index key dimension, quantization scales, causal boundaries, and selected-token count define the workload.

Long contexts offer more scoring work to remove, but pooled statistics must be maintained during cache insertion. Short contexts or small batches may not amortize routing and extra launches. Prefill needs query-dependent causal pooling; decode sees one growing history. FP8/FP4 index scoring, attention-cache quantization, and routed-head approximation create separate numerical effects. Results on one H200 do not establish gains on another GPU or accelerator.

## Implementation and remaining design space

The author's repository provides one-stage and two-stage vLLM patch packages. Its README specifies vLLM 0.17.0, Transformers 5.2.0, and TileLang 0.1.7.post3, with only one patch installed at a time. The two-stage kernels pool keys and route heads, then score selected candidates using all heads. A separate query-norm routing option changes the selection rule. This is an author-maintained custom-model/operator integration, not evidence of support in every upstream vLLM release.

Investigate whether its existing candidate-block path can express head routing without an independent cache protocol. Compare head-axis routing with token-block routing: the former reduces arithmetic across all history, while the latter tries to avoid reading parts of history. A combined selector might save more traffic but compound recall errors. Exact distributed top-k merging is a different mechanism: it preserves the chosen score ordering and should not be conflated with approximate candidate pruning.

## Discriminating experiments

Start from real indexer tensors captured at several layers and query positions. Compare score error, top-k overlap, missed high-attention-mass tokens, and routing latency against the current exact scoring path. Include adversarially sparse relevant keys within otherwise irrelevant pooling blocks. Measure key bytes read as well as arithmetic; a faster dot product can leave top-k or cache traffic dominant.

Then evaluate full-model retrieval, multi-hop reasoning, long-code use, and realistic document questions, not just one needle test. Compare plain routing and reranking at equal final top-k, measuring pooled-key maintenance and both selection stages. Service runs should sweep context length and concurrency while separating indexer, sparse MLA, and other model time. Report quality and latency together; paper kernel speedups and token-set overlap are not service improvements.

## References

- [DeepSeek-V3.2 report, v1](https://arxiv.org/html/2512.02556v1): indexer formula, training, top-k, and MLA relationship.
- [MISA, 2026-05-08, v1](https://arxiv.org/html/2605.07363v1): pooled-key head routing, reranking, complexity, and empirical fidelity.
- [Author implementation README at `dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc`](https://github.com/MuLabPKU/TransArch/blob/dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc/MISA_preprint/README.md), [two-stage kernels](https://github.com/MuLabPKU/TransArch/blob/dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc/MISA_preprint/misa_vllm_patch_2stage/misa_vllm_patch/misa_ops.py), and [indexer wrapper](https://github.com/MuLabPKU/TransArch/blob/dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc/MISA_preprint/misa_vllm_patch_2stage/misa_vllm_patch/indexers.py): released patch scope and actual routing/reranking.
- [vLLM indexer at `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/layers/sparse_attn_indexer.py): scoring/quantization/top-k and candidate-block execution at this revision.
