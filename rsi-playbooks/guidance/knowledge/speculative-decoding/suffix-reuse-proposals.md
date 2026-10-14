<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reuse suffix continuations without trained draft weights

English | [简体中文](suffix-reuse-proposals_zh.md) | [Speculative decoding](README.md)

## When history is a useful drafter

Code edits, repeated agent turns, and repeated rollouts often contain continuations already present in the prompt or previous outputs. A lightweight proposer can search these token sequences instead of running a second neural model. The useful question is whether history predicts the next span cheaply enough to justify target verification. Shared prefixes alone do not answer it: prefix-cache reuse saves processing of known inputs, whereas suffix speculation predicts unknown output.

Suffix Decoding uses one target model, no auxiliary neural model, and no newly trained weights. It matches the current trailing tokens against indexed histories and uses continuation frequencies to rank proposals and adapt depth. It is different from self-speculation through skipped model layers or adapters: those still perform neural computation and may require architecture-specific training.

The original report describes a CPU-resident global suffix tree of earlier outputs alongside a per-request tree for the active prompt/generation. Its candidate structure can be a compact tree. The current vLLM guide describes adaptive numbers of draft tokens per request. A research report's tree construction does not prove that a deployed proposer passes that same tree to its engine verifier; inspect the installed adapter's returned layout before designing a tree experiment.

## One iteration and the correctness boundary

Start with a committed token prefix. Search its suffix in the per-request and permitted history indexes. Select likely continuations, with a maximum depth and frequency/path scores. Hand the actual proposed sequence or tree to the target's existing verifier. The target evaluates the correct causal histories, accepts an allowed prefix/path, samples its correction or bonus, and commits only those outputs. Index committed generation, not rejected speculative text. Subsequent lookup must use the committed suffix.

Counts estimate usefulness, but are not automatically the stochastic proposal distribution. A deterministic selected token is a point-mass proposal even if an index assigns it a frequency below one. Exact token-wise verification can accept that proposal with target probability p(token), and rejection corrects using the target distribution excluding that token. If a proposer actually samples from frequency counts, the verifier instead needs that normalized realized proposal distribution. Passing heuristic frequency as q for a deterministic proposal breaks this distinction; see [sampling and correction](sampling-and-correction-cost.md).

For a small unmeasured example, history contains `return total` seven times and `return None` three times. After `return`, a deterministic proposer chooses `total`; its q is not 0.7. If the target assigns `total` probability 0.4, a point-mass sampler accepts with probability 0.4. A genuinely sampled frequency proposal has a different acceptance/correction calculation. The target still preserves its own output distribution when the proposal is weak.

## Costs, applicability, and current support

Per-step cost is lookup + candidate extraction + host/device transfer + target verification + correction. Expected useful span depends on match length, repeat frequency, and changes to identifiers or syntax after the match. A long reused span can be excellent; a false early match can pay verification for many discarded positions. The original report adapts speculation size using matched-prefix length and ranks paths by multiplied continuation frequencies.

This method is attractive when there are no suitable draft weights, the workload has actual repeated output, and lookup remains small relative to a target step. It can lose on novel prose, high-entropy sampling, histories with many ambiguous continuations, or saturated services where CPU indexing and synchronization become bottlenecks. Increasing history can improve coverage while increasing resident memory, update time, and lookup tail latency.

At vLLM commit `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`, suffix speculation is already integrated through Arctic Inference. The documented extra dependency is `arctic-inference`; `num_speculative_tokens` is a maximum, not a promise that every request drafts that many positions. Prompt n-gram matching is also established support. Useful history scope and depth remain workload-dependent.

Global history is also a data boundary. Exact target verification protects output sampling, but does not automatically authorize retaining another tenant's generation or exposing it through diagnostics. Use an explicit permitted history scope and existing retention controls.

## Distinguishing experiments

Compare no speculation, prompt-only n-gram, request-local suffix reuse, and permitted cross-request suffix reuse with identical target and sampling. Construct repeated code edits with a single changed identifier, repeated outputs with divergent endings, and nonrepetitive controls. Run cold and warm history conditions separately; replaying all evaluation outputs into the index before the cold run would change the question.

Record suffix match length, lookup p50/p99, candidate depth, history memory, update/eviction time, host/device transfer, verified rows, and first rejected position. Check that cancellation and rejected drafts do not enlarge the committed-output index. Greedy matching and stochastic distribution comparison are complementary; a high reuse hit rate alone does not demonstrate correctness or speed.

Then sweep concurrency and history size while measuring TTFT, output intervals, completion time, throughput, CPU utilization, and SLO capacity. A useful follow-up is deciding whether longer history or longer matches actually improve committed tokens per total step time, and whether a cheap request-local proposer beats a much larger shared index.

## Sources and status

Checked 2026-10-14.

- [Suffix Decoding report](https://arxiv.org/html/2411.04975): request/global trees, continuation frequencies, and adaptive expansion (2024).
- [Pinned vLLM suffix guide](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/suffix.md): integration, dependency, and maximum-length semantics.
- [Arctic Inference](https://github.com/snowflakedb/ArcticInference) owns history indexing; use the installed adapter revision to determine its returned proposal layout and index lifecycle.
- [Pinned vLLM sampler](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/sample/rejection_sampler.py): point-mass proposals and residual correction.
