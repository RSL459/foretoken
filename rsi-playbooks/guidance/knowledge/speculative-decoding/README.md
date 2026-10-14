<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Speculative decoding

English | [简体中文](README_zh.md) | [Inference knowledge](../README.md)

Choose a mechanism by the cost or failure observed in the draft/verify/correct/commit cycle.

- Fixed speculation helps isolated requests but hurts capacity under load: [allocate verification budgets](adaptive-verification-budget.md) using existing dynamic schedules and adaptive verification, with runner, graph, and parallelism constraints.
- Good training accuracy does not produce long accepted rollouts: [align draft training with decoding](draft-training-and-alignment.md), distinguishing public EAGLE3 pairs, native MTP, and targets that need new trained weights.
- Extra branches cost more than the paths they rescue: [spend tree nodes on useful paths](tree-verification-frontiers.md), including SGLang tree/chain overlap-scheduler differences.
- Sequential draft forwards dominate the iteration: [parallel and diffusion drafting](parallel-diffusion-drafting.md), starting from published PARD/DFlash pairs and already merged DFlash2 integration.
- The workload repeats text but no trained draft is available: [reuse suffix continuations](suffix-reuse-proposals.md) through existing Arctic Inference integration, measuring lookup cost and history scope.
- Vocabulary processing and correction dominate after the target pass: [sampling and correction cost](sampling-and-correction-cost.md), comparing exact token-wise samplers and supported block verification.
- Parallel tokens look plausible individually but fail as a continuation: [joint block candidate selection](joint-block-candidate-selection.md). LiLiCorr has implementation support but no public draft weights according to the inspected engine documentation, so it remains a training/research starting point.

State storage and recurrent rollback are covered by [recurrent speculation replay](../attention-state/recurrent-speculation-replay.md). These notes focus on discarding uncommitted proposals and continuing from corrected history; attention-cache truncation alone does not restore every model architecture.

Preserve target/draft revisions, actual proposal distributions, sampling rules, proposed/verified/committed lengths, and scheduler mode. Pair stage timing with client TTFT, output intervals, completion time, throughput, and capacity under the chosen SLO.
