<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Grouped GEMM without unnecessary token materialization

English | [简体中文](tile-aware-grouped-gemm_zh.md)

## Problem and current boundary

A sparse mixture-of-experts (MoE) layer does not necessarily become fast when its arithmetic count falls. Small expert intermediate dimensions increase the importance of gathering activations, writing intermediate results, and reducing expert outputs. Optimizing only the matrix multiply can leave most of this cost untouched.

SonicMoE already implements gather-aware grouped GEMM and activation fusion. Its paper primarily evaluates training, including backward activation storage; those memory savings are not decode savings. Its optional token-rounding router changes token-to-expert selection. That is a training co-design technique, not a semantics-preserving replacement for an existing inference router. The reusable inference question is how to execute the original routing more efficiently.

## Execution mechanism

For `T` tokens with hidden width `H`, hidden states have shape `X[T,H]`, and each token selects `K` logical experts. Expert `e` receives `m_e` rows, with `sum(m_e)=T*K` when every route is valid. Let `row_e(t)` map original token `t` to its local row in expert `e`. Its gated feed-forward computation is:

```text
H_e = gather(X, token_indices_e) @ W1_e
A_e = SwiGLU(H_e)
Y_e = A_e @ W2_e
y_t = sum_{e selected by t} routing_weight[t,e] * Y_e[row_e(t)]
```

The first grouped GEMM has variable row count `M=m_e`, while its feature dimensions are fixed. SonicMoE loads routed rows directly into shared memory instead of writing a separate gathered activation tensor to HBM. It fuses SwiGLU into the first GEMM epilogue. The second GEMM writes contiguous expert outputs; a gather-and-sum kernel restores token order and applies routing weights.

This last separation is deliberate. On Hopper, a scattered global store can impede the overlap between epilogue I/O and the next matrix-multiply tile. A contiguous asynchronous store plus a separate reduction can beat an apparently more fused scatter. Fusion should remove expensive traffic, not merely reduce the kernel count.

Consider expert row counts `[1,17,129]` and a row tile of 128. The logical workload contains 147 expert rows, but tile capacity is `128+128+256=512` rows. This is an explanatory geometry, not a measured slowdown ratio: masked loads, Tensor Core operations, and weight reuse contribute differently. Preserve all 147 routes while comparing smaller tiles, gather fusion, and grouped work scheduling. Do not remove real rows to make the utilization statistic look better.

## Conditions and trade-offs

The checked implementation targets NVIDIA Hopper and Blackwell families through CuTeDSL, QuACK, and Triton. Hopper warpgroup ping-pong and Blackwell tensor-memory staging are architecture-specific implementations of overlapping matrix multiplication with I/O. They are not automatically portable to MetaX or AMD.

Use the same BF16 operands, activation, router normalization, and weight layout when isolating execution changes. The repository distinguishes interleaved gate/up weights from concatenated checkpoint weights. A wrong conversion can produce both faster execution and incorrect answers. Expert parallel dispatch may already deliver contiguous expert-major rows; in that case a second local gather optimization may have little work left to eliminate.

## Experiments that distinguish explanations

Replay one layer's real routing and activations, then construct uniform, highly skewed, and many-single-row assignments with the same total valid routes. Sweep total token counts from single-request decode to prefill-sized batches. Compare the complete routing-to-reduction interval, not grouped GEMM alone.

Record valid rows, tile capacity, gather traffic, GEMM duration, aggregation duration, launch gaps, and peak workspace. If gather fusion helps only before EP dispatch, the explanation is local materialization rather than a universally faster GEMM. If contiguous output wins despite one extra kernel, inspect asynchronous store overlap and reduction traffic.

Validate every candidate against the original layer and router, then run the full model through a real service. Compare unprofiled TPOT, TTFT, output lengths, and answer quality at concurrency one and sustained concurrency.

## Evidence and remaining work

Checked 2026-10-14: [SonicMoE paper](https://arxiv.org/abs/2512.14080), algorithms 1–4, sections 3–5 and appendices B/F; [repository](https://github.com/Dao-AILab/sonic-moe/tree/7396f3e604827d8186c2e16e64b28ee33d3defd0), including `sonicmoe/functional/forward.py` and `benchmarks/moe-cute.py`. Remaining work is target-engine integration and measurement with its actual dispatched layouts and small-batch shapes. Consult [parallel communication](../parallelism-communication/README.md) when dispatch determines the input layout.
