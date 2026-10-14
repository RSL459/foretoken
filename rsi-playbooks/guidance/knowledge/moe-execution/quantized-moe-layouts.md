<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Quantized MoE is a layout and reduction contract

English | [简体中文](quantized-moe-layouts_zh.md)

## Problem and current boundary

A checkpoint labeled FP4 or FP8 does not identify a complete executable MoE representation. Packed values, scale granularity, scale encoding, matrix orientation, routing-weight placement, and final reduction all affect correctness and speed. An optimization that changes only byte count can select a faster but wrong interpretation.

FlashInfer already implements multiple quantized fused-MoE and EP paths, including NVFP4, MXFP8, and FP8/FP4 DeepGEMM backends. Its current API explicitly distinguishes activation and weight formats. The remaining opportunity is to reduce conversion and communication cost in a supported path while preserving a declared numerical contract.

## Execution mechanism

Prepare expert weights and scales at initialization. NVFP4 uses blocks of 16; MXFP8 uses blocks of 32, with format-specific scale representations. Packed four-bit values occupy two elements per byte, but their scales and alignment increase the true byte count. The representation must be transformed into the kernel's expected orientation and scale layout before capture.

At each forward, route tokens using the model's actual scoring and normalization, dispatch or stage hidden states, quantize activations if required, run FC1 plus activation, prepare FC2 inputs, execute FC2, and combine the expert outputs. Moving quantization before dispatch can reduce transferred bytes; doing it after dispatch may avoid transmitting a format that the communication backend cannot handle. These are different producer-consumer contracts.

The checked TRT-LLM FP4 API accepts linear hidden-state scale layouts for its routed GEMM and rejects swizzled ones. A scale array with the right number of elements is not necessarily the right array. Similarly, gated weights must preserve the relationship between gate and up rows, including any padding.

Final reduction matters independently of the weight dtype. With BF16 wire partials, an explicit FP32 sum followed by one BF16 cast differs from unordered BF16 atomic accumulation. Quantizing each FC2 partial for transport adds another quantization round trip before an FP32 sum. FlashInfer exposes these choices; its tuning notes report numerical and performance trade-offs rather than treating all of them as equivalent.

For two partials `a` and `-a+delta`, a relative error measured only against their near-zero sum can be misleading. Inspect per-term magnitudes, absolute residuals, and whole-layer error. Moving router weighting before a low-precision operation also changes rounding, even when the real-number formula looks equivalent.

## Conditions and trade-offs

The current documented backend matrix is architecture-specific. SM100-family NVFP4 paths are not a claim of native Hopper FP4 or MetaX support. W4A16, W4A8, and W4A4 differ in activation precision, bandwidth, conversion work, and accumulation behavior. Some split W4A8 paths require feature dimensions aligned to 128; check the selected backend rather than applying that constraint to every MoE kernel.

Low precision helps small batches only if weight traffic or conversion dominates enough to repay packing and scaling overhead. Smaller wire payloads can lose when a different token-return schedule is required. Redundant experts must carry their scales along with weights during migration.

## Experiments and service validation

First separate layout correctness from quantization quality. Compare a plain dequantize-plus-FP32 MoE computation using the exact quantized operands against the kernel. Then compare those operands and model outputs against the original higher-precision checkpoint. Kernel agreement cannot establish that the checkpoint quantization preserves task quality.

Exercise uneven and empty experts, hot experts, gate/up conversion, padded dimensions, and cancellation-heavy outputs. Time initialization separately from per-forward quantization, dispatch, compute, combine, and output copies. Compare pre- and post-dispatch quantization with the same effective operands and transport settings wherever possible.

Run a real full-model service and report unprofiled TPOT, TTFT, output lengths, and task scores. Include long-context and mixed-load conditions because extra workspace can reduce KV capacity.

## Sources and remaining work

Checked 2026-10-14: FlashInfer commit [a8e747c3](https://github.com/flashinfer-ai/flashinfer/tree/a8e747c3c1f7dfe5d51fab3883824b15da6829b7), [MoE-EP architecture](https://github.com/flashinfer-ai/flashinfer/blob/a8e747c3c1f7dfe5d51fab3883824b15da6829b7/docs/design_docs/moe_ep_architecture.md), its SM100 tuning notes, and the [TRT-LLM FP4 API](https://docs.flashinfer.ai/generated/flashinfer.fused_moe.trtllm_fp4_block_scale_moe.html). Research remains in target-workload format choice, conversion placement, and numerical attribution. See [small-batch scheduling](small-batch-megakernel-scheduling.md) before selecting a wire format from a large-batch result.
