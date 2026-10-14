<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Allocate verification nodes by draft path confidence

English | [简体中文](allocate-verification-nodes-by-draft-path-confidence_zh.md) | [Speculative decoding](README.md)

## The optimization problem

A draft tree spends extra candidates on alternatives to a single predicted continuation. It can rescue an early wrong guess, but a target verification pass still computes every retained node while the response commits only one path. Tree size is therefore neither output length nor accepted length. The research question is where to spend a fixed node budget when branching also changes scheduling, attention execution, and graph shapes.

EAGLE-2's context-aware expansion is established work, and SGLang already exposes tree depth, branching factor, and verification capacity. For current learned drafters, confidence should rank complete reachable paths, and the deployment's tree-versus-chain choice must include the scheduler behavior it enables or disables.

One target model and one trained EAGLE auxiliary module suffice. Multiple branches are alternative executions of that module, not multiple draft models. The module must match its target; tree construction creates no training weights. EAGLE-3 can supply a newer trained module while retaining a tree-shaped outer proposal process.

## Generate, verify, correct, commit

Begin at a committed prefix. Expand promising frontier nodes with the draft module, retaining token probabilities and parent identities. EAGLE-2 ranks a node using the product of draft confidences along its root-to-node path. After expansion, rerank all nodes and retain the verification budget, with ancestor closure: a child is useless if its parent is absent. The paper's ranking gives ancestors at least their descendants' score, with shallow tie-breaking.

Flatten the retained tree for the target, but use positions and a tree mask that expose only the committed prefix and each node's ancestors. Sibling candidates must not attend to one another. Target logits represent separate causal histories, not a single sequence of flattened tokens.

In greedy decoding, follow target choices through available children; when no proposed child matches, emit the target correction and stop that path. In stochastic decoding, use the engine's actual tree sampling/correction algorithm, including proposal probabilities and sibling bookkeeping. Independent candidate p/q tests followed by selecting the longest apparently accepted branch are not a sufficient correctness argument. Commit the chosen accepted path and correction/bonus output; discard siblings and descendants outside that path. The next iteration sees only this committed history.

## Cost model and an example

For N verified nodes, a useful objective is expected committed path length divided by draft expansion time plus target verification time(N, prefix lengths, mask/backend) plus sampling and compaction. Sum of node survival estimates is an expansion heuristic, not universally the expected output of an arbitrary stochastic tree verifier: branches are mutually exclusive and the coupling matters.

Suppose an unmeasured eight-node tree spends six nodes below a root candidate with confidence 0.3. Every descendant inherits that uncertainty; adding a strong alternative at depth one may be more useful than another deep node. Conversely, a highly predictable code continuation can favor a narrow deep chain. Two trees with eight nodes can have very different expansion launches, ancestor work, attention masks, and committed lengths. The target LM head still produces candidate rows for nodes that never become output.

At SGLang commit `e9400c5a8f3a0d0312a37aecef694f5edfd69341`, `--speculative-num-steps`, `--speculative-eagle-topk`, and `--speculative-num-draft-tokens` control depth, branching, and capacity. Leave all three unset for automatic selection or set all explicitly. With topk=1, capacity is adjusted to steps+1. The documented overlap scheduler supports topk=1, whereas explicitly wider trees require a different scheduling path. Thus a fair tree study must report overlap status; an apparent tree loss may actually be lost host/device overlap.

## Experiments and open questions

Use a compatible public EAGLE3 pair and keep the exact target/draft checkpoints fixed. Compare a chain and narrow/wide trees at the same target-node budget, then compare their best service configurations separately. The first isolates allocation; the second measures the real deployment trade-off. Keep sampling thresholds at the exact defaults rather than quietly increasing acceptance with approximate verification.

Record nodes expanded versus retained, frontier depth, branch coverage at the first mismatch, target rows evaluated, chosen path length, compaction time, graph padding, and speculative memory. A trace should separate sequential draft rounds from parallel target work. Use uncertain early continuations, deterministic copied/code spans, and mixed batches: only one of these workloads can misleadingly favor depth or breadth.

Check greedy output equivalence under matched numerics, and stochastic distributions rather than same-seed text equality. Exercise cancellation and EOS on a non-first branch so that rejected branches cannot leak into output, counters, or subsequent positions. Then measure client TTFT tails, inter-token latency, completion time, throughput, capacity at the SLO, and memory-limited concurrency. No increase in tree acceptance alone establishes a gain.

Open design questions include confidence calibration after quantization, retaining a small useful frontier without extra synchronization, and whether the benefit of early branch alternatives exceeds the scheduler and layout cost. These are workload/implementation questions beyond the already merged tree algorithm. For non-attention state rollback, consult [recurrent speculation replay](../attention-state/reduce-recurrent-state-writes-with-replay-buffers.md) instead of assuming a retained node is a complete recoverable model state.

## References

- [EAGLE-2 paper, v2](https://arxiv.org/html/2406.16858v2): dynamic expansion, global path scores, reranking, and masks (2024).
- [Pinned SGLang guide](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx): current tree parameters and overlap constraints; [EAGLE worker](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/speculative/eagle_worker_v2.py) owns the worker execution path.
- [EAGLE-3 paper](https://arxiv.org/html/2503.01840) establishes the separately trained feature-conditioned draft source. See [training alignment](improve-draft-rollouts-through-self-conditioned-training.md) for that distinct responsibility.
