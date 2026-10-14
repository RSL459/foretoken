<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Attention and recurrent state

English | [简体中文](README_zh.md)

Choose an entry by the work that dominates attention execution or prevents safe reuse of model state.

- [Hide attention softmax cost through asynchronous pipelines](hide-attention-softmax-cost-through-asynchronous-pipelines.md): understand Blackwell softmax and rescaling bottlenecks after matrix multiplication becomes fast, then investigate actual shape dispatch and mixed-traffic interference.
- [Match MLA decode kernels to quantized cache layouts](match-mla-decode-kernels-to-quantized-cache-layouts.md): distinguish model-specific quantized layouts, sparse gathers, split reductions, and the FlashMLA compatibility boundary.
- [Reduce indexer cost with query-dependent head routing](reduce-indexer-cost-with-query-dependent-head-routing.md): investigate the historical-token scoring cost that remains after sparse MLA, including MISA head routing and its approximate-selection trade-offs.
- [Parallelize KDA prefill with chunked recurrence](parallelize-kda-prefill-with-chunked-recurrence.md): understand KDA's decay/update order, chunk-parallel prefill, recurrent decode, and state-layout handoff.
- [Reuse hybrid prefixes with aligned state checkpoints](reuse-hybrid-prefixes-with-aligned-state-checkpoints.md): align attention KV, recurrent state, and convolution state at reusable boundaries; weigh checkpoint copies against replay and capacity.
- [Reduce recurrent state writes with replay buffers](reduce-recurrent-state-writes-with-replay-buffers.md): amortize recurrent-state writes and commit accepted tokens without intermediate matrix snapshots, while preserving flush and export semantics.

Return to [inference knowledge](../README.md).
