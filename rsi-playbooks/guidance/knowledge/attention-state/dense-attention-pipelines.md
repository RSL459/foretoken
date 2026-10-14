<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Dense attention pipelines on asymmetric GPUs

English | [简体中文](dense-attention-pipelines_zh.md)

## Problem and upstream position

Faster Tensor Cores do not accelerate every part of attention equally. For long-context prefill, matrix products can become fast enough that exponentials, row reductions, probability conversion, and output rescaling dominate. Increasing the GEMM tile alone may increase register pressure or move the bottleneck to shared-memory traffic.

FlashAttention-4 addresses this hardware imbalance with asynchronous Blackwell pipelines, described in its March 2026 paper and implemented in CuTe-DSL. The remaining question is whether a particular model shape and serving batch reaches those paths efficiently.

## How the pipeline works

For a query tile, attention streams through key/value tiles instead of materializing the full score matrix. Initialize the running maximum, denominator, and unnormalized output as `m=-infinity`, `l=0`, and `O=0`. For scores `S` in the next tile, including the attention scale and mask:

```text
m' = max(m, rowmax(S))
a  = exp(m - m')
P  = exp(S - m')
l' = a*l + rowsum(P)
O' = a*O + P*V
final output = O/l
```

The rescaling of both `l` and `O` is essential. A later key tile may contain the largest score; omitting correction would over-weight earlier tiles. This execution preserves dense attention semantics up to floating-point arithmetic while avoiding quadratic score storage.

On Blackwell, asynchronous MMA writes intermediates to Tensor Memory. FlashAttention-4 overlaps two query tiles: Tensor Cores compute one tile while softmax warpgroups process another. A separate correction warpgroup rescales accumulated output, keeping vector work off the softmax critical path. Larger tiles amortize scheduling and row-statistic work, but require enough independent work to keep the pipeline occupied.

The paper also distributes exponential evaluation between hardware special-function units and polynomial/FMA-based evaluation. This is useful only when the latter uses otherwise available resources. Its conditional rescaling policy lets the chosen softmax reference lag small maximum increases, reducing expensive vector corrections while preserving consistent normalization. It is not permission to discard denominator updates. Activation rounding and exponential approximation remain numerical considerations even though tokens are not sparsified.

## Conditions and trade-offs

The examined fast path targets Blackwell-class CUDA devices; Hopper or non-CUDA accelerators need their own implementation, not copied launch parameters. In the pinned interface, SM100/SM110 forward dispatch accepts FP16/BF16 and selected FP8 formats, with explicit head-dimension restrictions. FP8 output is BF16, and descales have their own shape contract. A BF16 head dimension of 128 is not equivalent to absorbed MLA dimensions or an FP8 path.

Short queries, small batches, irregular sequence lengths, GQA packing, paged storage, causal masking, and split-KV can select different schedules. Two-CTA cooperation may help a large tile but waste resources when there are already many independent query blocks. Faster prefill can also increase contention with simultaneous decode; isolated kernel throughput does not establish better service latency.

## Implementation and remaining design space

Start at the pinned CuTe interface and `FlashAttentionForwardSm100`, then inspect the selected tile, Q staging, split count, and 1-CTA/2-CTA decision. The implementation is available upstream. The paper notes related techniques in cuDNN 9.13 onward; that does not establish that every engine or model dispatches to FlashAttention-4.

Useful research questions concern shape-aware scheduling, ragged-batch load balance, and the conversion/packing work surrounding attention. For example, does increasing a key tile reduce softmax overhead but extend the tail of one unusually long request? Does an engine spend the saved kernel time preparing metadata? Keep these changes in the operator or its engine adapter, not a second attention implementation in the serving layer.

## Discriminating experiments

First compare supported implementations with identical Q/K/V tensors, mask, scale, dtype, and output tolerance. Sweep query length separately from key length: full prefill, short continuation prefill, and single-token decode exercise different parallelism. Include both uniform and ragged batches. Use kernel counters to separate Tensor-Core activity, exponential/vector work, memory traffic, and pipeline stalls; measure compilation and graph capture separately from steady-state execution.

Then run full-model prefill with the actual head dimensions and cache layout, followed by mixed long-prefill/short-decode traffic. Compare TTFT tails, decode TPOT, successful throughput, and memory capacity. Numerical evaluation should include extreme logits and long sequences, then model answer quality. A kernel win that disappears in metadata preparation or harms decode interference identifies the next owner rather than proving a service gain.

## Sources and checked state

Checked 2026-10-14.

- [FlashAttention-4, March 2026, v1](https://arxiv.org/html/2603.05451v1): forward pipeline, software exponentials, conditional rescaling, and reported comparisons.
- [CuTe interface at `1fc0221183e799363001394a12dd9e78e15f5dda`](https://github.com/Dao-AILab/flash-attention/blob/1fc0221183e799363001394a12dd9e78e15f5dda/flash_attn/cute/interface.py): actual architecture, dtype, shape, and schedule dispatch.
- [SM100 forward implementation at the same revision](https://github.com/Dao-AILab/flash-attention/blob/1fc0221183e799363001394a12dd9e78e15f5dda/flash_attn/cute/flash_fwd_sm100.py): asynchronous pipeline and correction-stage ownership.
