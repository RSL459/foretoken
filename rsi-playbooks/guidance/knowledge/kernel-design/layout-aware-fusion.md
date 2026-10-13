<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Layout-Aware Fusion Across Operator Boundaries

English | [简体中文](layout-aware-fusion_zh.md)

Investigate fusion when a layer repeatedly materializes, reshapes, or rereads intermediate tensors around otherwise efficient kernels.

## Begin with the actual producer and consumer

A normalization or activation can be fast in isolation yet expensive as a sequence of allocations, launches, and full tensor passes. If an intermediate has `N` elements of `s` bytes, removing its standalone write and subsequent read can avoid roughly `2Ns` bytes of logical memory traffic. Actual HBM savings depend on cache residency; this estimate is a hypothesis, not a measured bandwidth result.

Fusion only realizes that saving when the producer's output layout and the consumer's access pattern fit. A matrix accumulator is distributed across lanes for matrix instructions, not necessarily for coalesced output. CUTLASS epilogues explicitly exchange data and perform conversion before storing it. Adding a reduction or a second consumer can extend live ranges and require extra shared-memory traffic.

## An existing fusion exposes the useful boundary

vLLM v0.31.0 already contains a Q/K normalization plus rotary-position fusion pass. It recognizes packed QKV, splits Q and K, normalizes each head, applies RoPE, and replaces the sequence with a fused operation that mutates the packed buffer before splitting the result. It is not simply concatenating two arbitrary kernels.

The inspected pass accepts FP16/BF16, requires discovered attention geometries, and restricts head dimensions to 64, 128, or 256. It registers specific normalization epsilon and rotary-layout cases. It normalizes view/reshape representations so equivalent graphs can match. These details explain why a fusion can exist upstream yet not run for a particular model.

A useful investigation starts by checking matched graph sites and the actual dispatched kernel. If the pass is already active, introducing an equivalent replacement is unlikely to help. If it is inactive, distinguish a harmless graph-pattern difference from a real layout, dtype, aliasing, or mathematical incompatibility.

## Where further design is meaningful

Possible questions include writing directly into the next consumer's layout, combining normalization with an output conversion, or retaining values in registers across an epilogue. Each proposal must preserve every consumer of the original tensor. In-place transformation is unsuitable when another branch still needs the pre-transformation value.

Fusion also trades launch and memory savings against register pressure, occupancy, and loss of library specialization. A very efficient standalone GEMM plus a small epilogue may outperform a large fused kernel. Decode and prefill can choose different boundaries because their matrix sizes and launch-to-compute ratios differ.

## Experiments

Capture real tensors before the candidate sequence, preserving strides, aliasing, head geometry, and consumer uses. Compare the entire sequence, including allocations or copies introduced by the replacement. Check edge shapes and numerical differences from changed reduction order. Use repeated model steps to expose accidental mutation of residuals or caches.

Inspect the compiled graph and device trace to verify that the intended fusion runs. Measure whether removed operations actually reduce total layer time, then evaluate full-service performance. If the compiler already fuses the sequence, study its generated layout or scheduling rather than counting source-level operators.

## Sources and implementation state

Checked 2026-10-14.

- [vLLM v0.31.0 QK norm/RoPE fusion pass](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/compilation/passes/fusion/qk_norm_rope_fusion.py): existing implementation and matching conditions.
- [Existing vLLM fusion passes](https://github.com/vllm-project/vllm/tree/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/compilation/passes/fusion): inspect the relevant pass before proposing another one.
- [CUTLASS epilogue and memory organization](https://github.com/NVIDIA/cutlass/blob/main/media/docs/cpp/efficient_gemm.md).
- [PyTorch custom operator integration](https://docs.pytorch.org/tutorials/advanced/cpp_custom_ops.html): mutation and metadata contracts needed to make a fused kernel visible to the compiler.
