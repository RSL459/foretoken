<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Parallelize KDA prefill with chunked recurrence

English | [简体中文](parallelize-kda-prefill-with-chunked-recurrence_zh.md)

## Problem and upstream position

Linear attention replaces a growing per-token cache with a fixed-size recurrent matrix. Decode reads and updates that matrix for every active request, layer, and token, making state traffic a significant cost. Prefill processes many tokens at once and needs a parallel formulation of the dependent updates.

Kimi Delta Attention (KDA), introduced in the October 2025 Kimi Linear report, extends Gated DeltaNet (GDN) with channel-wise forgetting. Flash Linear Attention (FLA) already implements both chunk and fused-recurrent paths, including backend-specific adapters. Further optimization concerns state traffic, layout, numerical behavior, and variable-length execution.

## What one token does

Use key-first state orientation `S` with shape `[K,V]`. Treat `q`, `k`, `v`, `r`, and `o` as column vectors. The normalized key `k` and query `q` have length `K`, value `v` has length `V`, channel decay `alpha` has length `K`, and update strength `beta` is scalar. Here `q` includes the model's output scaling:

```text
A  = diag(alpha)
Sd = A*S
r  = v - transpose(Sd)*k
S' = Sd + beta*k*transpose(r)
o  = transpose(S')*q
```

Equivalently, `S' = (I - beta*k*k^T)*A*S + beta*k*v^T`. The residual update removes the value already predicted along the current key before adding the new value. This prevents repeated keys from accumulating indefinitely as in a simple additive memory.

For a two-channel example, `alpha=[0.99,0.10]` preserves the first state row while strongly forgetting the second. GDN's scalar decay cannot make that distinction within one head. The order matters: decay first, compute the residual against the decayed state, then update. Moving the diagonal decay across `k*k^T` generally changes the result.

During decode, one fused kernel executes this update and readout for each active sequence. During prefill, KDA groups tokens into chunks. Cumulative diagonal decay and low-rank corrections define dependencies within a chunk; a triangular transformation produces auxiliary matrices so the inner work can use parallel matrix products. Only the boundary state must pass sequentially between chunks. This trades some temporary computation and storage for Tensor-Core-friendly execution without replacing the model recurrence.

## Conditions and trade-offs

KDA is a trained architecture, not a runtime switch that turns an ordinary transformer into linear attention. Kimi Linear mixes three KDA layers with one global MLA layer, retaining explicit-history attention periodically. Consequently, total model state is not constant with context: MLA history still grows.

The cited FLA chunk API supports chunk sizes 32 or 64 and key dimensions up to 256. It requires an FP32 initial state when supplied; activations commonly use BF16. Log-space gates, raw gates transformed in-kernel, and post-sigmoid beta are different API contracts. Passing one representation as another changes forgetting behavior.

The default final-state layout is `[N,HV,K,V]`, with a value-first option. Packed variable-length sequences use `cu_seqlens`. The public fused-recurrent wrapper does not expose every lower-level state-indexing and accepted-token argument. An engine adapter must not assume that the ordinary public function already owns continuous-batching slot management. Backend presence also does not prove feature or performance parity across CUDA and Ascend.

## Implementation and remaining design space

Read the FLA chunk and fused-recurrent APIs together with the model's gate-generation path. Resolve query/key head sharing, value-head count, normalization, layout, and final-state ownership before changing kernels.

Promising questions include whether a state layout favors both recurrent readout and chunk-state handoff; whether gate and normalization fusion removes launches at low batch; and whether a shape-specific chunk schedule improves ragged prefill without padding excessive work. These should reuse existing backends. If recurrent matrix writes dominate high-batch decode, [replay-based state representation](reduce-recurrent-state-writes-with-replay-buffers.md) addresses that separate mechanism; scalar-decay GDN replay cannot be assumed to support KDA's channel decay unchanged.

## Discriminating experiments

Compare chunk and recurrent execution on the same token stream, initial state, gate values, normalization, and output scale. Feed a prefill-produced final state into decode; a layout error can remain hidden when both tests start from zero. Include repeated keys, sharply different channel decays, long streams, empty-padding slots, and variable-length packing.

Profile short decode and long prefill separately. Measure state bytes moved, register use, temporary chunk storage, and inactive-slot work, not only token throughput. Then evaluate the real hybrid model at several context lengths and concurrency levels. Separate KDA time from MLA and MoE time, inspect long-context retrieval and continuation quality, and check that recycling one request slot does not leak state into another. Relate precision and service results to the measured KDA fraction of model time.

## References

- [Kimi Linear, 2025-10-30, v1](https://arxiv.org/html/2510.26692v1): KDA recurrence, diagonal-plus-low-rank chunk execution, and hybrid architecture.
- [FLA chunk API at `1fe52b5d05c53601885610fab3d39157647d836d`](https://github.com/fla-org/flash-linear-attention/blob/1fe52b5d05c53601885610fab3d39157647d836d/fla/ops/kda/chunk.py): gate contracts, state precision, packing, and chunk restrictions.
- [FLA fused-recurrent implementation at the same revision](https://github.com/fla-org/flash-linear-attention/blob/1fe52b5d05c53601885610fab3d39157647d836d/fla/ops/kda/fused_recurrent.py): update order, state orientation, and public/lower-level API distinction.
