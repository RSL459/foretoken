<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Speculative decoding

English | [简体中文](README_zh.md) | [Inference knowledge](../README.md)

Choose a mechanism by the cost or failure observed in the draft/verify/correct/commit cycle.

- Fixed speculation helps isolated requests but hurts capacity under load: [Balance speculative work through adaptive verification budgets](balance-speculative-work-through-adaptive-verification-budgets.md) using existing dynamic schedules and adaptive verification, with runner, graph, and parallelism constraints.
- Good training accuracy does not produce long accepted rollouts: [Improve draft rollouts through self-conditioned training](improve-draft-rollouts-through-self-conditioned-training.md), distinguishing public EAGLE3 pairs, native MTP, and targets that need new trained weights.
- Extra branches cost more than the paths they rescue: [Allocate verification nodes by draft path confidence](allocate-verification-nodes-by-draft-path-confidence.md), including SGLang tree/chain overlap-scheduler differences.
- Sequential draft forwards dominate the iteration: [Remove serial draft forwards with parallel blocks](remove-serial-draft-forwards-with-parallel-blocks.md), starting from published PARD/DFlash pairs and already merged DFlash2 integration.
- The workload repeats text but no trained draft is available: [Avoid neural drafting by reusing suffix continuations](avoid-neural-drafting-by-reusing-suffix-continuations.md) through existing Arctic Inference integration, measuring lookup cost and history scope.
- Vocabulary processing and correction dominate after the target pass: [Reduce correction cost with fused rejection sampling](reduce-correction-cost-with-fused-rejection-sampling.md), comparing exact token-wise samplers and supported block verification.
- Parallel tokens look plausible individually but fail as a continuation: [Improve draft coherence through joint candidate selection](improve-draft-coherence-through-joint-candidate-selection.md). LiLiCorr has implementation support but no public draft weights according to the cited engine documentation, so it remains a training/research starting point.

State storage and recurrent rollback are covered by [Reduce recurrent state writes with replay buffers](../attention-state/reduce-recurrent-state-writes-with-replay-buffers.md). These notes focus on discarding uncommitted proposals and continuing from corrected history; attention-cache truncation alone does not restore every model architecture.

Preserve target/draft revisions, actual proposal distributions, sampling rules, proposed/verified/committed lengths, and scheduler mode. Pair stage timing with client TTFT, output intervals, completion time, throughput, and capacity under the chosen SLO.
