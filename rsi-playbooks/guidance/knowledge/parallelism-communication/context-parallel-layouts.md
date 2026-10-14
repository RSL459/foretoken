<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Context parallelism starts with tensor ownership

English | [简体中文](context-parallel-layouts_zh.md)

## Problem and current boundary

Long-context prefill distributes many query tokens; decode distributes access to a large history for very few new queries. They need different communication patterns. Calling both sequence or context parallelism (CP) can hide whether the implementation shards queries, heads, KV history, or only intermediate activations.

Unified Sequence Parallelism (USP) already combines Ulysses all-to-all with ring attention. Its paper studies primarily training and long-sequence attention, not continuous decode serving. vLLM already implements decode CP (DCP), and current source also contains prefill-CP cache gathering. Its deployment guide describes prefill strategies as under development. Availability depends on the backend, model, and worker implementation.

## Execution mechanisms

Ulysses starts with sequence-sharded Q/K/V. An all-to-all transposes ownership so each rank receives a longer sequence for fewer heads. Local attention processes those heads, and an inverse all-to-all restores sequence ownership. Head divisibility limits the straightforward implementation, especially with few KV heads or TP already dividing them.

Ring attention keeps query shards local and circulates KV blocks. Each rank accumulates partial attention with a numerically stable running softmax. USP constructs two orthogonal groups: Ulysses within one dimension and ring exchange within the other. The product of their degrees equals total sequence-parallel degree. An example is Ulysses degree two and ring degree four across eight ranks. Place frequent all-to-all on a faster domain and ring exchange on a slower boundary only when actual compute can hide it.

Causal work is not uniform across contiguous query chunks. Early queries see little history; late queries see much more. USP's zigzag assignment pairs early and late chunks. Original positions, RoPE, causal masks, and output reconstruction must follow the same permutation. Rearranging token storage is not permission to change model order.

Decode CP instead leaves each rank with a KV-history shard, computes local attention partials, and merges them with softmax normalization. If local normalized outputs are `o_r` and their log-normalizers are `lse_r`, a conceptual merge is:

```text
L = logsumexp_r(lse_r)
o = sum_r exp(lse_r - L) * o_r
```

An empty shard has `lse_r = -inf` and contributes no mass; the merge skips its undefined normalized output. Averaging local outputs without these weights is wrong. With a small query, ring prefill's abundant query computation no longer exists to hide transfers.

For one KV head and TP eight, plain TP can duplicate history eight times. The vLLM guide describes DCP within that existing TP group to reduce duplication, without adding GPUs. This is a cache-ownership change, not simply a faster collective.

## Conditions and trade-offs

USP's original measurements are BF16/FP16 training and attention workloads. Current YunChang supports multiple attention implementations, including forward-only alternatives; that does not establish paged-cache serving integration or native support for every accelerator.

DCP can increase cache capacity but introduces query/output communication. Its documented TP/head relationship is a starting constraint; actual backend support and speculative-query handling matter. PCP may replicate KV after gathering even when query work is sharded. In current vLLM `pcp.py`, PCP-only sharded decode requests gather other owners' new KV to preserve complete replicas; a distinct DCP combination keeps decode queries replicated. Measure memory ownership instead of inferring it from the CP name.

## Experiments and service validation

At fixed total ranks, vary Ulysses/ring degrees, context length, KV-head count, and causal layout. Compare maximum per-rank attention time, actual communication, temporary KV footprint, and position-correct outputs. Include short sequences where launch and reshape overhead can exceed savings.

For decode, sweep history length and concurrency independently; include uneven shard lengths, empty shards, cache growth, and speculative queries. Record cache capacity, attention time, merge time, and resulting TPOT. Distinguish capacity-enabled throughput from a faster single-request decode step.

Run a full service with long prompts, prefix reuse, and multi-turn cache growth. Validate answer quality and positions before comparing unprofiled TTFT/TPOT.
## Sources and remaining work

Checked 2026-10-14: [USP paper](https://arxiv.org/abs/2405.07719), algorithms 1–2 and sections 3–5; [YunChang a5f8f600](https://github.com/feifeibear/long-context-attention/tree/a5f8f600d435ced180a97c91c68e87ff3cfb8f89); vLLM [CP guide at 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/serving/context_parallel_deployment.md) and [PCP cache operations](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/attention/ops/pcp.py). Remaining work is target-backend ownership tracing and serving validation.
