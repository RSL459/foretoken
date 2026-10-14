<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Prefix checkpoints for hybrid attention and recurrent models

English | [简体中文](hybrid-prefix-checkpoints_zh.md)

## Problem and upstream position

A transformer can reuse KV pages for a cached prefix. A hybrid model also needs the recurrent state produced after exactly that prefix, together with any convolution state. Keeping only the state at the end of the previous request is insufficient when two requests diverge earlier.

vLLM already supports aligned Mamba checkpoints and, in its v0.30.0 documentation, a fine-grained prefix-cache option with specific speculative-decoding requirements. Its current cache manager also handles partial-tail checkpoints and copy-on-write. The research opportunity is checkpoint placement and cost under real reuse, not adding a second prefix cache or claiming hybrid caching is unavailable.

## Why the resume boundary matters

Suppose requests share tokens 0–89, then diverge. Attention KV exists through position 90, but recurrent checkpoints are only available after positions 64 and 128. State after 128 has consumed different suffix tokens and cannot serve as state after 90. State after 64 is valid; replaying tokens 64–89 reaches the desired boundary.

A checkpoint must name a precise processed-token boundary. All attention groups, recurrent layers, and short convolution buffers must agree on that boundary before generation resumes. Full-attention KV coverage and recurrent checkpoint coverage have different shapes, so the usable cache hit is their intersection, not the longest hit reported by either one alone.

Checkpoint placement trades recomputation for memory and copying. With checkpoint interval `C`, a hit may replay up to roughly `C-1` tokens before reaching the shared-prefix end. More checkpoints reduce that work but require additional state snapshots, which can be large even though recurrent state does not grow per token during ordinary decode. If a checkpoint becomes a writable request state, copy-on-write prevents one continuation from changing the snapshot another request is using.

The allocator introduces a second geometry. vLLM groups compatible layers into a shared physical pool with equal-size pages. A large recurrent state can force attention block enlargement or padding to fit that geometry. Logical token intervals and physical page bytes are different quantities: making block size larger may improve packing while worsening prefix-hit granularity.

## Conditions and trade-offs

For hybrid models combining attention with Mamba/GDN, state components, layer ratios, dtypes, and snapshot size are model-specific. A large FP32 state can make frequent checkpoints expensive; a smaller attention cache does not imply cheap recurrent snapshots.

The v0.30.0 fine-grained option requires `mamba-cache-mode=align`, EAGLE/MTP on the Mamba group, and an explicit `prefix-match-unit` smaller than the Mamba block size. The match unit must divide the applicable cache block sizes; multi-module MTP is excluded by that documentation. Those are version-scoped prerequisites, not advice to enable speculation solely to make every hybrid workload cacheable.

A repeated static system prompt, multi-turn continuation, and random unrelated prompts have different checkpoint value. Scheduler chunk boundaries also determine when state can be exported. An application-level message boundary does not automatically correspond to a ready, reusable checkpoint.

## Implementation and remaining design space

At the pinned current vLLM revision, `MambaManager` owns aligned lookup, internal checkpoints, partial-tail caching, and pending copy-on-write transfers. Its state-block relocation and boundary offload paths show that publication, writable state, and transfer are separate lifecycle stages. Extend that owner rather than allowing a router or storage connector to invent a parallel state boundary.

Questions worth measuring include sparse retention of frequently reused boundaries, checkpoint placement at observed prefix divergence, and packing that avoids inflating attention blocks. First determine whether the examined engine version already provides the required checkpoint mode. A storage connector that transfers attention pages but omits recurrent or convolution state does not complete hybrid cache transfer. Transfer completion also must precede use of the checkpoint.

## Discriminating experiments

Build paired requests with shared-prefix lengths just before, at, and after an attention/Mamba block boundary. Compare cold execution, an aligned hit with replay, and a fine-grained hit. Use the same suffix with caching enabled and disabled, checking final state and output distributions—not merely a cache-hit counter.

Then vary scheduler chunking, cancellation before publication, concurrent divergent continuations, eviction, and slot reuse. These are concrete lifecycle events that can expose a mismatched boundary or shared-state mutation. Measure checkpoint bytes, copy time, replayed tokens, allocator padding, and usable hit length separately.

Finally run multi-turn and static-prefix services under an equal total memory budget, including unrelated traffic that causes eviction. Compare TTFT tails, successful throughput, and decode interference. A higher hit rate can still lose if state copying and capacity reduction outweigh recomputation saved. Router affinity is useful only for the complete reusable hybrid state, not attention KV alone.

## Sources and checked state

Checked 2026-10-14.

- [vLLM v0.30.0 automatic prefix caching](https://docs.vllm.ai/en/v0.30.0/features/automatic_prefix_caching/): fine-grained checkpoint option and exact documented prerequisites.
- [vLLM hybrid cache design](https://docs.vllm.ai/en/latest/design/hybrid_kv_cache_manager.html): shared pages, group allocation, prefix intersection, and documented experimental limits.
- [`MambaManager` at `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/single_type_kv_cache_manager.py): implemented aligned/fine-grained lookup, checkpoint retention, and copy-on-write lifecycle. Current code observations are not generalized to all releases.
