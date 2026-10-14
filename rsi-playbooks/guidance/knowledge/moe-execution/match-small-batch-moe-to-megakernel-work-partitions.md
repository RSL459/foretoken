<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Match small-batch MoE to megakernel work partitions

English | [简体中文](match-small-batch-moe-to-megakernel-work-partitions_zh.md)

## Problem and current boundary

Single-request decode can activate several experts while providing only one row to each. A large-batch grouped GEMM configuration may then spend more time loading weights and coordinating workers than doing useful arithmetic. Splitting communication and computation introduces launch boundaries; fusing them removes boundaries but also fixes the allocation of GPU resources inside one persistent kernel.

FlashInfer already exposes split dispatch/compute/combine and fused MegaMoE backends, with architecture- and dtype-specific configurations. Its current design also provides offline tuning and explicit capacity profiles. The opportunity is to select a work partition appropriate to actual live tokens and demonstrate where that partition beats the existing one.

## Execution mechanism

In a split layer, dispatch materializes expert inputs, a local kernel computes the two expert projections, and combine restores outputs to source ranks. A megakernel instead keeps communication and expert computation inside one execution. Different warps can stage tokens, issue matrix multiplication, execute epilogues, or return results. These roles share SMs, registers, shared memory, and memory bandwidth.

For very small `m_e`, a wider output-feature tile can increase unnecessary work or hold resources longer; more communication workers can reduce arrival delay but deprive expert compute of resources. FlashInfer's cited SM100 NVFP4 profiles use different output tile widths and token-return roles across capacity ranges: epilogue warps, reused dispatch warps, or standalone warps. These choices are already implemented. Their profile boundaries are empirical choices for particular shapes, not universal thresholds.

Separate buffer capacity `C` from live token count `T`. An allocation sized for `C=2048` can repeatedly execute only `T=8` tokens. Capacity controls storage and potentially compilation; live work controls useful arithmetic and routing. Tuning only a full-capacity batch can select the wrong kernel for every low-load step. The current architecture documents live-token-aware offline records and pre-created workspace profiles; older portions of the tuning notes still describe capacity-only selection. Use the cited code version and verify which profile actually executes rather than assuming all prose is synchronized.

## Conditions and trade-offs

The referenced mechanisms are NVIDIA-specific, with distinct SM90, SM100-family, and other backend paths. Compare within one supported architecture and quantization format. BF16, NVFP4, and MXFP8 backends do not form a numerically identical performance ranking.

A small decode batch may be weight-bandwidth-bound even when communication is fused. Fusing cannot create more token reuse. Conversely, at large batches an aggressive compute partition can pay off. The upstream tuning notes explicitly report small-batch cases where combine quantization or in-kernel reduction loses despite larger-batch wins.

Workspace profiles are not independent concurrency lanes: pooled storage must remain stream-ordered. Create and warm profiles before graph capture, and keep their storage alive until associated graphs retire. Do not run a collective compile-and-time search on the serving request path.

## Experiments and service validation

At fixed capacity, sweep live tokens `1,8,64,512`, plus fuller batches. Then hold live tokens fixed while increasing capacity. This separates scheduling effects from buffer sizing. Include uniform routing, a single hot expert, and rank-asymmetric arrivals; record actual expert-row counts rather than just request concurrency.

Measure input quantization, staging, kernel execution, output copies, and the slowest rank's completion. The upstream prestaged microbenchmark excludes per-forward activation preparation; reproduce that region only for comparison, then add the omitted work for service attribution. Inspect whether a candidate saves launch gaps, improves GEMM duration, or merely changes launch skew.

Validate router outputs and numerical behavior before deploying the full model. Compare concurrency-one TPOT and open-loop latency under fluctuating traffic, with graph coverage and model quality held explicit. A profile that improves saturated throughput but worsens low-load decode is a workload-specific option, not an unconditional default.

## References

FlashInfer [MoE-EP architecture](https://github.com/flashinfer-ai/flashinfer/blob/a8e747c3c1f7dfe5d51fab3883824b15da6829b7/docs/design_docs/moe_ep_architecture.md) and [SM100 tuning notes](https://github.com/flashinfer-ai/flashinfer/blob/a8e747c3c1f7dfe5d51fab3883824b15da6829b7/flashinfer/moe_ep/kernel_src/sm100/cutedsl_megamoe/TUNING.md), commit `a8e747c3`. Remaining work is resolving the active target-engine profile path and evaluating its low-load behavior. See [grouped GEMM](reduce-moe-materialization-through-gather-fused-grouped-gemm.md) for local I/O and [communication overlap](../parallelism-communication/hide-moe-communication-through-microbatch-and-block-overlap.md) for SM competition.
