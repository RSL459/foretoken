<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Vocabulary Selection and Sampling Pipelines

English | [简体中文](vocabulary-selection-sampling_zh.md)

Large-vocabulary filtering and sampling can remain significant after model-forward optimizations, especially when verification produces several rows per request. Selection algorithms and stage fusion reduce this post-forward work.

## Selection is not necessarily a full sort

For a probability row of vocabulary size V, top-k needs only the selected support, not a complete ordering of all V entries. Top-p then needs a cumulative mass boundary, and categorical sampling needs a draw from the retained distribution. Materializing full-vocabulary intermediates between these stages can add launches and repeated memory traffic.

FlashInfer's current CAKE path already implements a fused alternative. A thread-block cluster performs radix selection, cooperating through distributed shared memory, and writes a compact slab of up to 1,024 `(probability, index)` entries. A subsequent stage orders that slab, applies top-p relative to the top-k mass, renormalizes, and samples. For supported small-k cases, the final work can fuse into the first stage. Larger cases can use a dependent launch to overlap the second stage's prologue with the first stage's tail.

Dispatch by batch/vocabulary shape, integration copies, and the cost of competing selection algorithms determine when this pipeline is useful.

## Preserve the requested distribution

Filter order matters. With probabilities `[0.5, 0.3, 0.2]`, `k=2`, and `p=0.6`, top-k-first keeps mass 0.8, and the first entry alone exceeds `0.6 × 0.8 = 0.48`. Top-p-first on the original distribution needs the first two entries to exceed 0.6. The two procedures have different supports.

The inspected CAKE implementation specifies top-k-first semantics, deterministic index tie-breaking, fixed-point cumulative sums, and a Philox stream. Equal output distributions do not automatically imply identical sampled tokens under another implementation's random-number assignment. A replacement must preserve the interface's intended semantics and the task's reproducibility requirement.

Greedy decoding is a separate case: argmax does not require top-p filtering or probability renormalization. Its opportunity is often avoiding unnecessary full-vocabulary work while preserving logits processors and requested logprob outputs. A language-model head or probability tensor may still be needed by another consumer.

## Hardware and input envelope

The documented path uses contiguous float32 probability rows and Hopper-or-newer NVIDIA features. Unsupported inputs, disabled top-k, or k beyond its supported slab are routed to the existing deterministic sampling implementation. A generic entry point succeeding therefore does not prove that the specialized kernel executed. The API exposes a routing query for that purpose.

The total cost also includes logits-to-probabilities conversion, penalties, constraints, and any tensor-layout conversion. A tiny local sampling gain can disappear when the integration forces an extra float32 copy. For speculative decoding, compare time per committed token rather than time per candidate row; see [speculative decoding](../speculative-decoding/README.md).

## A useful experiment

Preserve actual batch size, vocabulary, filter values, and probability shape. Include peaked and flat distributions, tied boundaries, greedy requests, and heterogeneous per-row settings. Measure the complete filtering/sampling path in eager and graph replay, inspect actual dispatch, and compare distribution semantics separately from same-seed token identity.

## Sources and implementation state

Checked 2026-10-14.

- [CAKE sampling documentation](https://docs.flashinfer.ai/api/cake_sampling.html): support envelope, route query, and public APIs.
- [Pinned FlashInfer implementation](https://github.com/flashinfer-ai/flashinfer/blob/d6dd9f336dcd9e4820b1583d20077804fe61147c/flashinfer/cake_sampling.py): exact selection, tie, special-value, and fallback semantics.
- [FlashInfer sampling API](https://docs.flashinfer.ai/api/sampling.html): the existing alternatives used outside the specialized path.
