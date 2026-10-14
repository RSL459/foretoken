<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Diagnose generation divergence through fixed-prefix and task comparisons

English | [简体中文](diagnose-generation-divergence-through-fixed-prefix-and-task-comparisons_zh.md) · [Measurement and simulation](README.md) · [Knowledge](../README.md)

## Three questions need three comparisons

A kernel change can alter logits without changing the highest-probability token. A tiny logit change can also flip two nearly tied tokens, after which autoregressive generation follows different contexts. Neither observation alone establishes a change in task accuracy. Numerical fidelity, generated-sequence agreement, and answer quality are related but distinct questions.

Floating-point addition is not associative. Batched and sliced operations may choose different reductions or kernels, and reduced-precision arithmetic changes rounding. PyTorch's numerical-accuracy documentation explicitly does not promise bitwise identity across these execution arrangements. A fixed seed controls random choices; it does not fix reduction order or make greedy argmax insensitive to numeric perturbations.

## Why a small perturbation can flip greedy output

Let the reference's top two logits be z₁ and z₂ with margin m = z₁ − z₂ > 0. If every candidate logit differs by at most ε, the top choice is preserved when m > 2ε. When the margin is smaller, even a tiny change can reverse the order. This sufficient bound assumes the same vocabulary and prefix; a measured RMSE is not a bound on every component.

For illustration, logits 10.000 and 9.999 have margin 0.001. Perturbations of −0.0006 and +0.0006 flip their order. Softmax distributions can remain extremely close despite the token difference. Once that token enters the next prefix, subsequent differences include changed context, so attributing all later disagreement to the original kernel error is misleading.

## Fixed-prefix distributions isolate the local effect

Teacher forcing supplies identical token IDs at every compared position, preventing context drift. For reference probabilities p and candidate q, KL(p || q) = Σpᵢ log(pᵢ/qᵢ) weights disagreement by reference mass; total variation is ½Σ|pᵢ − qᵢ|. Top-1 agreement measures argmax stability, while top-k overlap measures changes among plausible alternatives. These metrics reveal different aspects of the same perturbation.

A full-vocabulary distribution is essential for a full-vocabulary KL claim. Top-k truncation omits probability mass; decoded text keys can collide for different token IDs. Foretoken's comparison client requests token-ID keys and checks vocabulary coverage and mass before normalizing serialization error. Both services need the same token-ID mapping, template, special-token handling, and model vocabulary. Otherwise the vectors may not represent the same prediction problem.

Common offsets do not change softmax. Centered-logit RMSE therefore removes a shared offset, but it can still emphasize changes to many very-low-probability tokens. Inspect high-KL positions, argmax margins, corpus-token probabilities, and task classes rather than declaring one metric sufficient. Short general-text windows do not establish behavior at a long-context retrieval boundary or in structured tool output.

## Free generation measures a different failure mode

Greedy sequence comparison exposes first-divergence position, EOS behavior, and exact agreement under actual feedback. It is useful for implementation changes expected to preserve token choices. Exact mismatch is not automatically quality loss: two continuations may both answer correctly. Conversely, high sequence agreement on easy samples can miss rare but consequential errors.

Batch invariance is an existing vLLM feature, currently documented as beta with hardware/model and tensor-parallel restrictions. It changes kernel choices and can cost performance. Use it as a diagnostic control within its supported scope. Open issue #51187 reports repeated concurrent workloads with differing logprobs but identical emitted token IDs in that reproduction; its cause remains unresolved.

## Experiments that separate error from instability

First repeat the unchanged reference under sequential and representative concurrent scheduling. This measures its own variability. Then compare the candidate on identical fixed prefixes across context lengths, batch shapes, precision, and graph modes. If errors appear only with a changed batch shape, inspect reduction or dispatch; if large errors cluster at a particular layer/state transition, investigate a correctness defect rather than accepting generic floating-point variation.

For early greedy divergences, score both models on the same pre-divergence prefix and examine the margin. Large local distribution shifts indicate a different problem from near-tie flips. Check native token IDs and finish reasons rather than retokenizing visible text. Finally run paired task evaluation with the same scoring rule and inspect changed answers, including long-context and structured-output cases relevant to the optimization. Quality, performance, and exact reproducibility should each retain their own conclusion; none substitutes for the others.

## References

- [PyTorch 2.9.0 numerical accuracy](https://github.com/pytorch/pytorch/blob/v2.9.0/docs/source/notes/numerical_accuracy.rst): batching, reduction order, backend precision, and non-bitwise guarantees; version-pinned text.
- [vLLM batch invariance](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/batch_invariance.md): beta scope and trade-offs; revision dated 2026-10-13. [Issue #51187](https://github.com/vllm-project/vllm/issues/51187): open, created 2026-08-05; report distinguishes logprob variation from token divergence.
- [Foretoken distribution comparison](../../../../benchmarks/docs/eval/distribution-comparison.md) and [comparison client](../../../../benchmarks/src/benchmarks/integrations/distributions.py): at `e6ae3df6`; teacher forcing, native greedy IDs, complete probability vectors, and metric formulas.
