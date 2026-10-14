<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Remove serial draft forwards with parallel blocks

English | [简体中文](parallel-diffusion-drafting_zh.md) | [Speculative decoding](README.md)

## Where the serial cost comes from

A fast target does not guarantee a fast speculative iteration. An autoregressive draft proposing K tokens can require K sequential auxiliary forwards, each with launch, attention, and output-projection overhead. Parallel drafting replaces this serial chain of computations with one block prediction. It does not make the target non-causal, and it does not guarantee that the block's independently plausible tokens form a useful continuation.

PARD and DFlash expose different ways to remove the dependency. PARD adapts an ordinary small autoregressive model to predict several future positions using mask placeholders. Its drafter does not consume target hidden representations and can be reused across compatible target models. DFlash is a separately trained lightweight block-diffusion drafter conditioned on selected target features. Both use one target plus one auxiliary model; neither is a no-training prompt-reuse method.

The original DFlash is especially concrete: a verified anchor starts a block, the remaining positions are masked, and a single draft forward predicts them together. Bidirectional interactions within the draft block are allowed. The target verification remains autoregressive and causal. “Diffusion” here must not be interpreted as an obligatory long iterative denoising loop; the evaluated drafting mechanism is a one-step block prediction.

## One cycle and training requirements

After target prefill or a previous commit, supply the anchor and committed context to the drafter. DFlash concatenates selected target-layer features, projects/normalizes them, and supplies them as extra keys/values to draft layers. Generate the unverified block positions in parallel. PARD instead constructs its mask-token prediction inputs from token-level context, without this target-feature interface.

Run the target once over the proposed linear continuation under a causal mask. In greedy decoding, accept matching target choices until the first mismatch and use the target correction. With probabilistic proposals, exact stochastic verification must receive the actual proposal distribution, not treat arbitrary raw slot logits as the realized joint sampler. Commit the verified prefix and correction/bonus; discard the rest. Extend the drafter's context using committed target features/tokens, not the whole unverified block.

DFlash training freezes the target, uses target-generated responses, selects clean anchors, and masks the future positions. Within-block bidirectional attention and separated training blocks match the proposal layout. Early-position loss weighting reflects the fact that a first error can invalidate many later drafts. PARD's adaptation uses future-position mask objectives and conditional drop-token training to reduce adaptation cost. Public weights are the shortest experimental path; changing the target does not automatically make a DFlash checkpoint compatible.

## Cost and deployed boundaries

For comparable expected commit length L, the serial path costs roughly K*draft_forward + verify(K) + correction, while a parallel path costs block_forward(K) + feature_handling + verify(K) + correction. The parallel forward can itself get more expensive with block width. Increasing K also inflates target rows, LM-head work, and buffers even if most positions are rejected.

An unmeasured example illustrates the distinction: reducing six draft forwards to one helps only if that block forward, feature path, and changed verification cost sum to less than those six forwards. An early disagreement can leave a 16-position block committing only one correction. Shortening verification then saves target work, not the draft forward already completed; see [adaptive verification](adaptive-verification-budget.md).

Current vLLM documentation already provides a PARD example using `amd/PARD-Qwen3-0.6B` with `parallel_drafting: true`. The official DFlash project lists public target-specific weights. DFlash2's local convolution and candidate selector are also already merged: vLLM #52816 and SGLang #35371. Use these integrations with their matching checkpoints.

At SGLang commit `e9400c5a8f3a0d0312a37aecef694f5edfd69341`, DFlash verifies a linear block, infers its size from the draft config when possible, and requires a draft window at least as large as the block. Its documented path excludes pipeline parallelism and DP attention, and disables overlap scheduling and mixed chunked prefill. Compare these actual execution modes rather than assuming every generic speculative configuration composes with DFlash. Native block-size conventions can include the anchor; vLLM's LiLiCorr guide explicitly counts speculative positions as trained block size minus one.

## Experiments and research space

First establish a working published target/draft pair and the intended engine revision. Compare no-spec, autoregressive EAGLE3, and parallel block drafting under matched sampling, outputs, and concurrency. Sweep block widths and context lengths. Profile draft layers, feature movement, vocabulary projection, target verification, correction, and graph/host gaps separately. Then run unprofiled service comparisons for TTFT, inter-token latency, completion time, throughput, memory headroom, and SLO capacity.

To distinguish serial-cost removal from better predictions, compare equal expected committed lengths where possible, and report actual proposed/verified/committed positions. Include short outputs, where startup/prefill dominates, and saturated mixed traffic, where verification consumes capacity. Changing scheduler overlap between methods belongs in the result, not a hidden experimental difference.

Remaining questions include maintaining block coherence, selecting context windows without damaging domain-specific continuations, and retaining engine features while packing variable-length verification. [Joint candidate selection](joint-block-candidate-selection.md) addresses coherence as a distinct mechanism.

## Sources and status

Checked 2026-10-14.

- [PARD v4](https://arxiv.org/html/2504.18583v4): parallel masks, target independence, and adaptation objectives; [pinned vLLM example](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/parallel_draft_model.md).
- [DFlash paper](https://arxiv.org/html/2602.06036): feature-conditioned one-pass drafting and training; [official repository](https://github.com/z-lab/dflash) at `07ebd93db9f472af339b644bb70221ad8428328a` lists public model collections.
- [vLLM #52816](https://github.com/vllm-project/vllm/pull/52816) merged 2026-08-21 as `b389ac29465b33f9e9c534df221ea3c129e9793f`; [SGLang #35371](https://github.com/sgl-project/sglang/pull/35371) merged 2026-08-19 as `c14312a66420b75ca9a11bf1817c4db1fa26b097`.
- [Pinned SGLang guide](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx) and [SpecForge training guide](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/docs/sections/basic_usage/training.md) establish current inference/training boundaries.
