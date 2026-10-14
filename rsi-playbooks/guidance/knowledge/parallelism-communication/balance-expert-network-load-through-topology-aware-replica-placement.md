<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Balance Expert and Network Load: Topology-Aware Replica Placement

English | [简体中文](balance-expert-network-load-through-topology-aware-replica-placement_zh.md)

## Problem and current boundary

An expert placement can balance token counts yet send too much traffic across a slow boundary. Conversely, preserving locality can leave one rank overloaded. The right objective includes both expert execution and the links that carry tokens, outputs, and migrated weights.

Topology-aware placement is already present in DeepSeek EPLB-derived algorithms: compatible logical expert groups are packed onto nodes, replicas are created within those nodes, and physical experts are packed across local GPUs. LPLB additionally exposes cube, hypercube, and torus replica graphs. Current DeepEP main already supports NVLink weight prefetch primitives for redundant experts. The remaining question is how to choose and evaluate these existing structures for actual routing and fabric contention.

## Execution mechanism

Start from the model's logical expert groups, routing selections, and measured rank connectivity. The cited vLLM default policy sums demand per group, packs groups to nodes, creates redundant experts within each node, and distributes the resulting per-copy load across its GPUs. If group/node divisibility does not permit this hierarchy, its implementation falls back to a global packing policy. That fallback is not evidence that locality remains protected.

Replication changes the physical destination graph without changing the logical router. A copy on a nearby GPU can absorb demand without introducing another network-domain crossing, but only if the dispatch assignment actually selects it. A copy on a remote node can balance arithmetic while increasing both dispatch and return traffic.

LPLB's `r2o` mapping explicitly expresses replica relationships. Its cube topology supports balancing within an eight-GPU subgroup; torus relationships can connect a local neighbor and a neighbor node. These graphs constrain which hot experts can share work and how many copies exist.

For an illustrative layer with hidden width `H=4096`, BF16 activations, and 1000 token-expert rows crossing a node boundary, the raw row payload is `1000*4096*2=8,192,000` bytes in one direction. This excludes metadata, scales, headers, alignment, and deduplication; if several chosen experts share a destination, a transport may avoid duplicating the input row. Returning outputs is a separate traffic leg. Count actual backend bytes rather than multiplying top-k blindly.

Newly selected replicas also need weights. DeepEP main's `lb_prefetch_weights` transfers weights and quantization scales over NVLink before expert compute, using caller-supplied redundancy mapping and reserved storage. All ranks in the domain participate, including those with no assigned slots. The primitive owns transfer completion; the caller still owns planning, token rerouting, and expert computation. It does not implement a complete serving replication policy.

## Conditions and trade-offs

The model's routing groups are not equivalent to arbitrary hardware groups. Changing model selection to force node locality changes behavior; remapping identical experts does not. Preserve logical routing and its weights when testing physical placement.

Topology depends on the visible GPU/NIC mapping, actual peer reachability, and competing traffic. Identical node counts do not imply identical communication domains. Intra-node replicas trade weight memory for locality; that memory competes with KV capacity. Frequent replication can move more bytes than it saves in token traffic.

Use numerical and representation equivalence for replicas, including all scale tensors. A trained router's bias update is a model change, not an interchangeable physical load-balancing mechanism.

## Experiments and service validation

At identical replica counts, compare hierarchical placement, global packing, and a feasible custom replica graph. Use uniform routes, node-local groups, a remote hotspot, and abrupt domain transitions. Record per-link dispatch/combine bytes, maximum link load, rank GEMM times, weight-transfer bytes, and cache capacity.

If equal token load coincides with a longer layer, inspect remote communication and nonlinear GEMM cost. If locality improves but rank skew worsens, identify the trade-off instead of averaging it away. Run other representative traffic on the fabric to test whether the placement survives shared-link contention.

Deploy the full model on the real topology and compare unprofiled TTFT/TPOT, successful throughput, quality, and latency during placement changes. Validate cancellation and empty-rank participation.
## References

vLLM [EPLB default policy at 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/eplb/policy/default.py); [LPLB 0490f794](https://github.com/deepseek-ai/LPLB/tree/0490f79452f7ef277e814449600b1b1dd4c663b3), README and mapping code; [DeepEP main 93eb6eb2](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509), redundant-expert exchange API. [DeepEP #500](https://github.com/deepseek-ai/DeepEP/pull/500) was merged into `antgroup-opt`, not main. Remaining work is measured joint compute/network placement. See [online assignment](../moe-execution/balance-batch-load-through-expert-replica-assignment.md) for the fast loop and [windowed balancing](../moe-execution/balance-expert-hotspots-with-windowed-replication-and-migration.md) for migration timing.
