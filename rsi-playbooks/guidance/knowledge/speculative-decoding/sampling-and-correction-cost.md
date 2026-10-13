<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Preserve target sampling while reducing correction cost

English | [简体中文](sampling-and-correction-cost_zh.md) | [Speculative decoding](README.md)

## The shared cost after verification

A speculative target pass is not the whole iteration. Vocabulary projection, sampling filters, residual distributions, random-number generation, output packing, and logprobs can consume substantial time and memory. These costs are shared across trained drafts, parallel blocks, and reuse proposals. The research opportunity is removing redundant work while preserving the actual target sampling semantics, or choosing an already available verifier whose increased vocabulary work earns a longer useful prefix.

Let p be the target's desired sampling distribution at the current causal history and q the distribution that actually generated a candidate x. Ordinary token-wise verification accepts x with min(1,p(x)/q(x)). On rejection, sample from normalized max(p-q,0); when every candidate succeeds, draw the bonus from the target distribution. This produces the target distribution, not necessarily the same text as a non-speculative run with the same seed.

One target and any existing proposer suffice. No additional trained verifier is required. A deterministic candidate has point-mass q; it is not a sample from its pre-argmax softmax. If penalties, temperature, top-k/top-p, or grammar constraints define the desired target behavior, p must reflect them at each candidate history. Proposal reranking also changes q. Correctness depends on these effective distributions, not just the target's raw logits.

## A concrete iteration

For an unmeasured two-token example, p=(0.6,0.4) and q=(0.8,0.2). Candidate A is accepted with probability 0.75; B is always accepted. If A is rejected, the positive residual is entirely B. Overall P(output=A)=0.8*0.75=0.6, matching p. Replacing that residual draw with an unconditional target draw would overproduce A.

Generate a chain and its actual proposal probabilities, then run causal target verification for all positions. Process target logits using each position's hypothetical prefix. Apply acceptance/correction, stop at the first rejected token in the token-wise algorithm, and pack the accepted prefix plus its correction or bonus. Commit only those outputs. Future-position logits computed after an earlier rejected proposal are not logits for the corrected history and cannot simply be emitted. Rejected speculative state must be rolled back before another cycle; see [recurrent speculation replay](../attention-state/recurrent-speculation-replay.md).

Block verification is a different exact coupling, not just parallel execution of independent token-wise tests. Current SGLang documentation says it evaluates all draft prefixes and can retain a longer prefix even when an earlier prefix check fails, using the corresponding correction distribution. Copying this behavior by skipping a rejected token would be wrong: its correctness comes from the block algorithm. The original paper is older work; current engine integration provides an alternative to measure, not a new algorithm to announce.

## Implemented boundaries and cost

The vLLM sampler at `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9` separates greedy argmax from random sampling. It applies speculative-history penalties and sampling constraints, computes recovered candidates for positions, and then chooses the valid emitted prefix. Its top-k/top-p helper warns about vocabulary sorting cost. Some correction work is deliberately done before knowing the first rejection to avoid synchronization; “unused computation” can still be faster than a host decision.

FlashInfer's fused chain API accepts draft probabilities [B,K,V], draft IDs [B,K], and target probabilities [B,K+1,V]. A hypothetical B=32, K=8, V=128000 float32 pair of dense probability tensors occupies about 278.5 MB in decimal units, before logits and buffers. This is a shape calculation, not measured memory. Reducing materialization or fusing passes can matter even with unchanged acceptance.

SGLang commit `e9400c5a8f3a0d0312a37aecef694f5edfd69341` documents exact block verification for stochastic EAGLE/EAGLE3/NEXTN with topk=1 and full target-vocabulary proposals, plus supported sampled DFlash/DSpark paths, on CUDA or ROCm. Greedy point-mass DFlash proposals gain no longer prefix from that algorithm. Block verification adds vocabulary reductions. Lowering the separate acceptance thresholds is not the same optimization and must not inherit the exact algorithm's distribution claim.

## Experiments and design questions

Separate three changes: fused implementation of the same token-wise rule, block versus token-wise verification, and probabilistic versus deterministic proposals. Otherwise gains cannot be attributed. Keep checkpoints, sampling, graph mode, context, and output limits fixed. Use small-vocabulary synthetic distributions locally to inspect the correction identity, then real model distributions with peaked and flat probabilities, filters, penalties, mixed greedy/random batches, EOS, and cancellation.

Measure projection, filtering/sorting, probability conversion, RNG, residual selection, output packing, and requested logprob time. Compare committed outputs per total iteration time, not accepted candidates per verifier invocation. FlashInfer's independent accepted count can include positions after an earlier rejection; its emitted-draft count is the actual prefix and excludes the bonus. Those counters cannot be substituted for one another.

For correctness, compare empirical next-token/prefix distributions and quality under the actual serving sampler. For performance, use unprofiled runs and report TTFT, inter-token latency, completion time, throughput, peak memory, and capacity at the SLO. An optimization that saves sampling time but changes output length or filtering is a different comparison.

Open questions include whether eager residual computation beats deferred computation without synchronization, how to avoid repeated full-vocabulary passes when logprobs are requested, and which stochastic workloads amortize block verification's extra reductions. They require measured kernel and service evidence.
## Sources and implementation boundaries

Checked 2026-10-14.

- [Pinned vLLM sampler](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/sample/rejection_sampler.py): processing, point-mass proposals, residual selection, and packing.
- [FlashInfer chain API](https://docs.flashinfer.ai/generated/flashinfer.sampling.chain_speculative_sampling.html): shapes, RNG offsets, and accepted/emitted counters. Match this rolling reference to the installed library version.
- [Pinned SGLang guide](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx): supported block-verification combinations and vocabulary-reduction cost.
- [Block Verification Accelerates Speculative Decoding](https://arxiv.org/abs/2403.10444) defines the original algorithm; the pinned engine guide above defines the serving boundary.
