<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Make parallel draft candidates jointly coherent

English | [简体中文](joint-block-candidate-selection_zh.md) | [Speculative decoding](README.md)

## A different problem from parallel drafting

Parallel block prediction removes serial auxiliary forwards, but per-position plausibility is not joint plausibility. A draft can predict an opening identifier and a later use of a different identifier, even when each token is locally common. Target verification rejects the inconsistent prefix, so a high marginal accuracy can coexist with short committed spans. Joint candidate selection studies how to spend a small amount of extra draft computation on consistency before paying for target verification.

LiLiCorr builds on a DFlash auxiliary model rather than introducing another full language model. There is one target, one DFlash backbone, and a learned correlator head. DFlash2 also already supplies a trained candidate selector and local convolution; the broad idea of adding candidate dependence is not absent from engines. The mechanisms and checkpoint requirements must be distinguished rather than calling every selector LiLiCorr.

This is presently a training/research candidate, not a ready deployment recipe: the inspected SGLang documentation explicitly states that no LiLiCorr drafter is published yet. Implemented loading support does not supply the learned correlator weights. A user with only a plain DFlash checkpoint should use that existing path, not invent a compatible head by changing its architecture name.

## Mechanism and one cycle

Given a committed prefix and verified anchor, DFlash produces top-k token candidates at every unverified block position. LiLiCorr jointly processes the candidate lattice with a small bidirectional transformer. It assigns candidates incoming and outgoing vectors; adjacent-position pair compatibility is computed through their similarity. Batched pair scores require no serial neural forward for every chosen token. A left-to-right walk selects a path through the lattice, conditioned on prior choices.

The original paper trains with oracle-prefix cross-entropy and a target-weighted penalty against distractors, co-training the DFlash backbone and correlator. Candidate coverage matters: a selector cannot recover a target token absent from the candidate set. A pretrained plain DFlash module plus an untrained correlator therefore does not satisfy the method's assumptions.

After selecting or sampling the chain, run ordinary causal target verification. If selection is deterministic, proposal q is a point mass at each chosen token. If the walk samples, provide the normalized conditional distribution used at each visited lattice step, not the backbone's unary probabilities. Accept and correct according to the exact verifier, commit the accepted chain and correction/bonus, then discard all unused lattice paths and rejected suffixes. The target is still responsible for correctness; the correlator only tries to make proposals cheaper per committed token.

## Cost and diagnostic example

For m candidate positions and k candidates each, adjacent pair scoring has roughly (m-1)*k*k edges, in addition to lattice encoding. At m=15 and k=8, that is 896 pair scores; this unmeasured count is not the head's runtime because transformer attention, projection, candidate embeddings, and graph folding also matter. Increasing k can improve coverage while making the lattice much more expensive.

Consider a two-position draft where each position's unary accuracy is 0.8. Under a simplified independent-error example, both positions match with probability 0.64. A correlator can improve their consistency without improving either marginal, or worsen the first position while improving later ones. Useful diagnostics therefore include the first-failure position and cumulative prefix survival, not just average slot accuracy.

On the same prefixes reached by the selector, distinguish a coverage miss from a ranking error: the target token was outside top-k versus inside top-k but not chosen. Teacher-forced covered accuracy uses an easier population than self-conditioned rollout. The SpecForge guide explicitly separates those populations and says its fixed recorded-block metrics are training diagnostics, not stochastic serving acceptance. A high oracle top-k length is a coverage bound on those blocks, not a promised service speedup.

## Current implementation and experiments

Pinned vLLM documentation at `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9` requires `LiLiCorrDraftModel`, complete geometry/head weights, and Model Runner V2. Its trained block includes an anchor, so a block of 16 normally maps to 15 speculative tokens. Longer lengths lack learned slot embeddings; shorter lengths use a prefix and still require measurement. Probabilistic proposal sampling uses the request temperature and reports the realized distributions. LiLiCorr-specific block-rejection GPU validation and its adaptive-verification combination are documented as pending; support in shared machinery is not an end-to-end result.

SGLang uses `DFLASH` with checkpoint-selected LiLiCorr architecture rather than a separate algorithm flag. It warns about host sequence-length synchronization and eager fallback head execution, both of which can erase a small selector gain. These are deployment costs distinct from the paper's coherence mechanism.

Without trained weights, begin with a training plan and candidate-coverage analysis, not a claimed service experiment. If compatible weights become available, compare plain DFlash, the trained selector, and probabilistic selection at identical block width, target/draft revisions, and sampler settings. Match training investment when comparing trained variants. Ablate k and compute coverage/ranking splits on identical reached prefixes. Record lattice/head time, graph versus eager steps, feature transfer, memory, first-failure position, and actual committed length.

Then measure unprofiled client TTFT, inter-token latency, completion time, throughput, SLO capacity, and output quality. Inspect sampled output distributions independently of acceptance improvements. Remaining questions include whether the head's marginal gain pays for lattice work, how candidate sets should change by domain, and how graph folding interacts with quantized projections.
## Sources and status

Checked 2026-10-14.

- [LiLiCorr paper](https://arxiv.org/html/2608.20530): lattice encoding, compatibility vectors, path selection, and training objectives.
- [Pinned vLLM guide](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/lilicorr.md): checkpoint requirements, length conventions, proposal sampling, and pending validation.
- [Pinned SGLang guide](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx): public-weight availability and graph/backend conditions.
- [SpecForge training guide](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/docs/sections/basic_usage/training.md): DFlash2 selector objectives and coverage/ranking diagnostics, distinct from a LiLiCorr training recipe.
