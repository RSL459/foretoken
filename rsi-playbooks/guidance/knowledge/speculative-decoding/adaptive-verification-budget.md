<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Allocate speculation by verification cost

English | [简体中文](adaptive-verification-budget_zh.md) | [Speculative decoding](README.md)

## Problem and mechanism

A fixed draft length buys fewer target decode iterations by spending more work per iteration. That exchange changes with concurrent requests, context length, and available compute. A policy that wins for an isolated request can reduce service capacity even when its acceptance rate does not change. The useful optimization target is committed output per unit of occupied service time, not the fraction of proposals accepted.

There are two distinct decisions: how much to generate and how much to verify. With an autoregressive auxiliary drafter, stopping early can save subsequent draft forwards. With a one-pass parallel drafter, truncating its output usually saves verification work but not the already completed draft forward. Adaptive verification therefore uses one target and its existing model-based drafter; it does not require a second auxiliary model. Proposals remain chains or linear blocks, and changing their admitted lengths does not itself change the rejection-sampling rule.

For request r, let a[r,j] estimate acceptance at position j conditional on its predecessors surviving. Its position-j survival estimate is s[r,j] = product(a[r,1..j]); K[r] is the admitted draft-prefix length. A useful batch objective is approximately:

```text
expected committed tokens / step time
= sum_r (1 + sum_j<=K[r] s[r,j])
  / (draft time + verify time(total admitted slots, contexts) + correction/commit time)
```

The extra one represents the correction or bonus output of an ordinary chain iteration, away from EOS and output limits. It is an accounting convention, not an extra accepted draft. Choosing only the largest individual confidence can violate prefix dependencies; the selected lengths must describe contiguous prefixes.

For an illustrative, unmeasured example, suppose requests A and B have survival estimates [0.9, 0.8, 0.7] and [0.5, 0.2, 0.05]. A four-slot budget can allocate three slots to A and one to B, yielding 2.9 expected accepted drafts, rather than 2.4 for two slots each. This is advantageous only if packing, graph padding, estimation, and state bookkeeping do not consume the saved time.

## One iteration and current implementation

Generate a block using the existing draft model. Estimate position survival, select a batch budget from measured step costs, and admit each request's prefix. The target evaluates only admitted proposals with their correct causal histories. Verification accepts a prefix and samples a correction, or appends a target bonus when the whole admitted prefix succeeds. Commit those outputs; discard every uncommitted proposal, including drafted positions that were never verified. The next draft must start from the committed history, not the longest generated block.

At vLLM commit `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`, adaptive verification is already documented for EAGLE, MTP, DFlash, DSpark, and standalone draft models. DSpark can provide a trained confidence head; other drafters use an online logistic estimator calibrated from verification outcomes. Startup profiling supplies a step-cost curve.

The same snapshot requires full CUDA graphs and attention backends that tolerate device-decided query lengths. LoRA and pipeline parallelism are excluded. The default synthetic profile context is 8192 tokens; a much longer deployed workload can invalidate that cost estimate. The separate batch-size schedule, `num_speculative_tokens_per_batch_size`, already supports reducing K or setting it to zero, but its documentation excludes data parallelism because independent ranks can select divergent collective schedules. Do not conflate this schedule with per-request device-side allocation.

## Experiments that distinguish policies

First compare no speculation, a fixed length, and the existing batch-size schedule. Then compare fixed drafting with adaptive verification. Keep target/draft revisions, sampling, output distributions, graph mode, and scheduler constant. Use both homogeneous requests and batches mixing easy repetitive outputs with difficult reasoning; an aggregate acceptance percentage hides the allocation opportunity in the latter.

Sweep offered load through saturation and include short and long contexts. Capture proposed, admitted, reached, accepted, and committed positions separately, estimator calibration by position, actual versus captured graph size, draft/verify/sampling time, and wasted target rows. Measure client p50/p99 TTFT, inter-token latency, request completion, output throughput, errors, and sustainable request rate under the chosen SLO. Changing K during an iteration, cancellation, EOS, and a zero-draft step deserve direct execution because they exercise the metadata and commit boundary.

The remaining research question is not whether adaptation exists. It is whether a deployed workload's context-dependent cost and calibrated survival estimates justify finer allocation than a simple load schedule. Poor calibration during domain shifts, stale startup curves, and graph rounding are concrete places to investigate. State recovery belongs to [recurrent speculation replay](../attention-state/recurrent-speculation-replay.md).

## Evidence and status

Checked 2026-10-14.

- [Pinned vLLM adaptive verification guide](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/adaptive_verification.md) and [dynamic schedule guide](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/dynamic_speculative_decoding.md) define this snapshot's support boundary.
- [PR #47808](https://github.com/vllm-project/vllm/pull/47808), confidence-scheduled verification, merged 2026-08-12 as `7f7a32cfec0f1bc5b73c37200b86631523a1ea8f`.
- [RFC #48202](https://github.com/vllm-project/vllm/issues/48202): contributor-reported low-load null results and saturation-sensitive motivation. Its linked [PR #48692](https://github.com/vllm-project/vllm/pull/48692) is closed without merge; current support is described in the pinned guide above.
