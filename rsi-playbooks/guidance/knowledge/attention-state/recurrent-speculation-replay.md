<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Replay buffers for recurrent decode and speculative commit

English | [简体中文](recurrent-speculation-replay_zh.md)

## Problem and upstream position

A recurrent layer retains a matrix per request rather than token-wise KV. Conventional decode reads and writes that entire matrix each step. Speculative verification may additionally retain intermediate states so rejection can restore the accepted prefix. At high batch, those bytes can dominate even though history length no longer determines the recurrent-state size.

ReplaySSM's October 9, 2026 paper represents state as a checkpoint plus recent input records. SGLang already merged ordinary-decode integration in PR #28451 on June 26 and speculative integration in #28695 on July 20, following earlier public work. The separate compact-cache PR #27658 was still open when checked. The remaining opportunity is workload-specific representation and lifecycle cost.

## Mechanism: avoid materializing every state

Use value-first state `S` with shape `[V,K]`, where `V` and `K` are the value and key dimensions. Column vectors `v_t` and `d_t` have length `V`; `k_t` and the scaled query `q_t` have length `K`. Scalars `alpha_t` and `beta_t` control decay and update strength. A scalar-decay GDN update can be expressed as:

```text
d_t = beta_t * (v_t - alpha_t*S_previous*k_t)
S_t = alpha_t*S_previous + d_t*transpose(k_t)
o_t = S_t*q_t
```

After `h` records since checkpoint `S0`:

```text
S_h = (product_i alpha_i)*S0
    + sum_j (product_{i>j} alpha_i)*d_j*transpose(k_j)
```

The output needs `S_h*q`, not the entire stored matrix. A kernel can read `S0`, multiply it by the query, and add buffered low-rank contributions without writing `S_h` to HBM. Every `L` committed records, a flush folds the records into a new checkpoint. This amortizes full-state writes; it does not eliminate the checkpoint read on every step.

For GDN, `d_t` depends on the previous state. A verification chunk therefore computes the coupled corrections through a triangular transformation rather than treating draft records as independent additive updates. Suppose three drafts are verified and only the first two are committed. The next logical state includes checkpoint history plus those two records; the third remains outside the committed cursor and is overwritten. No full snapshot at the third position is needed. Accepted-length conventions must specify whether the bonus token is included.

Flush ordering is part of correctness. Rejected records cannot enter the permanent checkpoint. Prefix-cache publication may force materialization even when the replay window is not full. In the examined SGLang implementation, circular-buffer cursors, request-slot indexing, raw cached inputs, and accepted-length handling adapt the paper to serving; this is not a verbatim paper kernel.

## Conditions and trade-offs

This is primarily a bandwidth optimization for large recurrent states and sufficient batch. Batch-one decode may be launch- or compute-bound, and replay work can outweigh fewer writes. A hybrid model with dominant MoE or full attention may show little end-to-end gain even if its GDN kernel improves.

Increasing `L` reduces flush frequency but increases buffer reads and reconstruction. The scalar-decay formulas for Mamba-2 and GDN require a different replay derivation for KDA's channel-wise gates. State orientation, activation dtype, checkpoint precision, and dot-product precision all affect the selected kernel.

The paper also separates a high-precision recurrence checkpoint from a lower-precision output-read checkpoint. For GDN, it retains raw `v_t` inputs so flush can recompute the coupled `d_t` corrections from the high-precision checkpoint, rather than reuse corrections derived from low-precision reads. Flush then casts the reconstructed state independently into both checkpoint copies. Low-precision readout rounding therefore affects outputs without feeding back into the next permanent recurrence checkpoint. Evaluate those output changes on the target model's tasks.

## Implementation and remaining design space

Start at SGLang's pinned `gdn_replayssm_spec_decode.py`, the GDN backend, and state-pool cursor ownership. The checked verify implementation is linear-chain oriented; tree verification is a separate design question. The open compact-cache PR is also distinct from the already merged replay verification path.

Measure whether adaptive flush timing, buffer layout, or precision separation helps the actual batch distribution. Prefix checkpoint export, slot reuse, cancellation, graph capture, and state transfer must understand buffered state. Copying only `S0` while dropping committed records loses recent tokens. A complete transfer can either materialize the state or transfer the checkpoint and its committed records coherently; the existing engine owner should choose the representation.

## Discriminating experiments

Compare direct recurrence and replay for the same initial state and token stream, including flush boundaries and rejection at every position of a short verify chain. Check outputs and post-commit state. Exercise partial-window checkpoint export and immediate slot reuse; verify that rejected records cannot reappear after the next flush.

For performance, separate non-flush, flush, and forced-publication steps. Sweep batch, replay length, draft length, and accepted-prefix distribution, recording state bytes read/written and reconstruction time. A mean kernel latency can hide flush spikes.

Then run the actual hybrid model with the same draft mechanism, sampling configuration, and memory budget. Compare TPOT tails, successful throughput, acceptance, and quality; include ordinary decode to identify gains due to replay rather than speculation. Report GDN's fraction of model time to relate the recurrent-kernel change to the complete-model result.

## Sources and checked state

Checked 2026-10-14.

- [ReplaySSM v1](https://arxiv.org/html/2610.13778v1), [submission record](https://arxiv.org/abs/2610.13778): submitted 2026-10-09; recurrence, replay, speculation, and precision separation.
- [SGLang RFC #28511](https://github.com/sgl-project/sglang/issues/28511): closed; integration scope and model-dependent reported results.
- [PR #28451](https://github.com/sgl-project/sglang/pull/28451): merged at `a10a24e9a7fdc0ddcc7dc3e90c0d4983707db028`; [PR #28695](https://github.com/sgl-project/sglang/pull/28695): merged at `c41c573ce9ed2053d38aa711582e19a67a5e9755`; [PR #27658](https://github.com/sgl-project/sglang/pull/27658): open, not used as evidence of shipped compact-cache support.
- [Actual verify kernel at `e9400c5a8f3a0d0312a37aecef694f5edfd69341`](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/kernels/ops/attention/fla/gdn_replayssm_spec_decode.py): circular replay, folding, commit conventions, and precision paths.
