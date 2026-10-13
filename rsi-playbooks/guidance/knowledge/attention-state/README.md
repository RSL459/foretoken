<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Attention and recurrent state

English | [简体中文](README_zh.md)

Choose an entry by the work that dominates attention execution or prevents safe reuse of model state.

- [Dense attention pipelines](dense-attention-pipelines.md): understand Blackwell softmax and rescaling bottlenecks after matrix multiplication becomes fast, then investigate actual shape dispatch and mixed-traffic interference.
- [MLA cache layouts and decode scheduling](mla-cache-layouts.md): distinguish model-specific quantized layouts, sparse gathers, split reductions, and the FlashMLA compatibility boundary.
- [Sparse indexer routing](sparse-indexer-routing.md): investigate the historical-token scoring cost that remains after sparse MLA, including MISA head routing and its approximate-selection trade-offs.
- [Channel-gated recurrent state](channel-gated-recurrent-state.md): understand KDA's decay/update order, chunk-parallel prefill, recurrent decode, and state-layout handoff.
- [Hybrid prefix checkpoints](hybrid-prefix-checkpoints.md): align attention KV, recurrent state, and convolution state at reusable boundaries; weigh checkpoint copies against replay and capacity.
- [Recurrent decode and speculative replay](recurrent-speculation-replay.md): amortize recurrent-state writes and commit accepted tokens without intermediate matrix snapshots, while preserving flush and export semantics.

Each entry identifies already available upstream mechanisms separately from remaining research questions. Sources and integration states were checked on 2026-10-14.

Return to [inference knowledge](../README.md).
