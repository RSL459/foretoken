<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Grouped LoRA kernels: ragged tiles and low-rank parallelism

English | [简体中文](grouped-lora-kernels_zh.md) | [Multiple models and adapters](README.md)

## What remains after multi-LoRA batching exists

Punica and S-LoRA established shared-base execution with grouped low-rank updates. That capability is already available in current engines; implementing “multi-LoRA batching” again is not a new research direction. The interesting work is shape-specific execution: small ranks expose little parallelism, packed QKV projections have unequal output widths, and inactive adapter slots can still occupy a launch grid.

A concrete current candidate is SGLang PR #41951. At the checked date it is open, not merged. It proposes compact expand grids and opt-in split-K shrink. Its implementation and numerical constraints are more informative than a generic claim that grouped GEMM is faster.

## One adapted linear layer

Let X have shape [m,h], base W shape [o,h], and adapter i use A_i=[r_i,h], B_i=[o,r_i]. The layer computes Y=XW^T+s_i(XA_i^T)B_i^T for rows belonging to adapter i. Base GEMM handles all rows together. Adapter metadata groups rows, shrink computes a rank-sized intermediate, and expand scatters the update into the appropriate base-output rows. Requests using the base model alone receive no adapter update.

For a packed QKV layer, Q may be wider than K and V. A rectangular expand grid sized to the largest slice launches tiles beyond smaller slices. Early return avoids math but not the launch/scheduling work. The proposed compact grid flattens only valid slice tiles using existing CPU-known offsets; it avoids copying device metadata back to the host.

Shrink has the opposite problem: small m and r can leave many SMs idle while reducing over a large h. Split-K divides that reduction across independent programs, writes FP32 partials, and launches a reduction before casting the final intermediate. This increases parallelism but adds memory traffic and another launch. The PR's automatic opt-in policy is narrowly measured for BF16 rank 32, input widths 4,096 or 12,288, and particular tile parameters. It is not a universal dispatch rule.

## Models, precision, and weights

Use a compatible released base checkpoint and PEFT-style LoRA weights trained for that checkpoint's target modules, rank, and scaling. No training is needed for the kernel change. Random A/B tensors are useful numerical probes but cannot establish model-quality preservation. Actual adapters may update embeddings, attention, MLP, or MoE experts, changing shape and sharding requirements.

The inspected vLLM shrink implementation accepts FP16/BF16 inputs and matching LoRA weights, with FP32 partials in batch-invariant execution. A quantized base model does not imply quantized adapter support. Tensor parallelism changes local projection widths and must be included in the shape specification. The SGLang proposal reports H200 validation; other NVIDIA GPUs, ROCm, or MetaX require their own supported path and measurements.

Split-K changes summation order. The proposal leaves deterministic inference on the original path and reduces only live rows and rank columns, avoiding uninitialized graph-padding data. Quality equivalence must therefore be evaluated at the intended numerical standard rather than assumed bitwise.

## A discriminating experiment

Compare the checked main path, compact expand alone, split-K alone, and both changes. Cover low ranks, mixed ranks, ragged QKV widths, empty slices, small decode batches, large prefill batches, and adapter-popularity skew. Run the proposal's public kernel benchmark as an entry point, but include routing and metadata preparation in separate full-model measurements.

Record live versus launched tiles, shrink/expand/reduction duration, scratch bytes, SM utilization, graph replay behavior, and numerical error against FP32 matmul. Then measure per-adapter TTFT, TPOT, output length, errors, and SLO-compliant request throughput with real adapters. Check base-only and adapter requests after slot reuse to expose stale updates.

If compacting helps only unequal slices, the gain is eliminated empty work. If split-K helps only tiny batches but regresses prefill, dispatch should remain shape-specific. If a kernel gain disappears in service latency, base GEMM or queueing dominates. The remaining candidate is measured dispatch and ragged-grid efficiency, not reintroducing foundational grouped execution.

## Sources and checked state

Checked 2026-10-14.

- [SGLang PR #41951](https://github.com/sgl-project/sglang/pull/41951): `OPEN`, `mergedAt=null`, head `a7deef700821501c37fd1de266d4f1f42848d23a`; body and production-file diff. Contributor results are not Foretoken results.
- [SGLang LoRA documentation](https://docs.sglang.io/advanced_features/lora.html): current Triton/CSGMV, batching, and graph restrictions. Main checked at `e9400c5`, dated 2026-10-13. [PR #42299](https://github.com/sgl-project/sglang/pull/42299) merged 2026-10-03; its kernel reorganization is existing state, not a candidate.
- [vLLM shrink source](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/lora/ops/triton_ops/lora_shrink_op.py): grouped metadata and precision path at `6849ca6`, dated 2026-10-13.
- [S-LoRA, arXiv:2311.03285v1](https://arxiv.org/html/2311.03285v1): ragged-rank execution and paging as foundations, not recent candidates.
