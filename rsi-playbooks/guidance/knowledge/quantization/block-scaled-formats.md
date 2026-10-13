<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Block-scaled formats and kernel layouts

English | [简体中文](block-scaled-formats_zh.md)

A four-bit checkpoint can reduce memory traffic while leaving arithmetic at sixteen bits. The useful question is not whether a model is “FP4,” but which operands the selected kernel consumes, how their scales are loaded, and whether conversion happens once or on every forward pass.

## Representation becomes an execution schedule

For a linear layer, write `Y = X Wᵀ`, with `X[M,K]` and `W[N,K]`. A block quantizer stores `q` and reconstructs each element as `w ≈ s_block q`. FP8 can use tensor, channel, or block scales. ModelOpt documents per-channel weights with dynamic per-token activations, as well as block-FP8 weight-only checkpoints. Those choices have different metadata access and activation-conversion costs even when weight storage is eight bits.

MXFP4 stores E2M1 values with an E8M0 power-of-two scale for each 32-element block. NVFP4 uses 16-element blocks with FP8 block scales and a wider-range outer scale. They share a four-bit value type, not a scale encoding or packing contract. Ignoring padding and outer scales, their weight costs are approximately `4 + 8/32 = 4.25` and `4 + 8/16 = 4.5` bits per element. A nominal bit count therefore understates both checkpoint size and runtime traffic.

Execution proceeds through checkpoint decoding, optional one-time repacking, activation quantization, tiled GEMM, scale application, and the output epilogue. A native W4A4 kernel consumes low-bit operands; a W4A16 kernel loads compressed weights but computes with higher-precision activations. Materializing the whole dequantized matrix before multiplication sacrifices the memory advantage. Dequantization inside a tile can preserve it, but conversion instructions still cost time.

For example, take `M=1, K=N=4096`. Each weight is used once, so weight reads dominate a dense projection. At `M=256`, each loaded tile is reused by many tokens; arithmetic throughput and activation conversion become more important. A W4A16 path can win at the first shape and lose at the second without either result being contradictory.

## Current integration and remaining choices

The checked vLLM ModelOpt documentation already describes NVFP4 automatic backend selection and a Marlin W4A16 path when native FP4 GEMM is unavailable. Its current MXFP4 source already performs backend-specific weight/scale conversion, padding, and modular MoE dispatch. GPT-OSS MXFP4 configuration leaves ordinary linear layers unquantized; the presence of an MXFP4 expert checkpoint does not establish full-model W4A4 execution.

SGLang also documents automatic FP8/FP4 kernel selection and explicit backend overrides. Kernel dispatch, block quantization, and checkpoint loading are existing facilities, not proposals. Useful remaining work concerns the target model's small-M versus large-M crossover, expert shape distribution, conversion placement, and padded dimensions. Native Blackwell NVFP4 and AMD CDNA4 FP4 paths must be assessed separately from older-device weight-only or converted-format execution. Support for one dtype name does not imply equal instruction support across these devices.

## A discriminating experiment

Extract the actual projection and routed-expert shapes, including strides, group sizes, scales, and padding. Compare the existing native low-bit kernel, the available weight-only kernel, and BF16 for `M=1`, a few decode batch sizes, and representative prefill chunks. Include activation quantization and epilogues in timing, while reporting one-time repacking separately. Inspect memory traffic, selected backend, and output error against the same BF16 inputs.

Then compare complete services with identical model semantics, workload lengths, and concurrency. Observe TTFT, TPOT, successful output tokens, quality, and available device memory. A smaller model may admit more requests and improve throughput without improving single-request decode. If the local gain disappears, inspect scheduling, attention, and collectives rather than claiming four-bit arithmetic was ineffective.
## Sources

Checked 2026-10-14; source identities are recorded in the [category index](README.md).

- [vLLM ModelOpt formats and backend selection](https://docs.vllm.ai/en/latest/features/quantization/modelopt/).
- [vLLM MXFP4 implementation at the checked commit](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/layers/quantization/mxfp4.py).
- [SGLang quantization and dispatch](https://docs.sglang.io/advanced_features/quantization.html).

[Quantization questions](README.md) · [Knowledge index](../README.md)
