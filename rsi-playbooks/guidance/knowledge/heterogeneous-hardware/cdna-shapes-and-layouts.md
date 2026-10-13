<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# CDNA shapes, layouts, and matrix throughput

English | [简体中文](cdna-shapes-and-layouts_zh.md)

A matrix kernel tuned for a large prefill batch can be inefficient for decode or sparsely populated experts. On AMD CDNA, shape-specific matrix instructions, wavefront scheduling, local data share (LDS) use, and scale layouts matter more than copying a launch configuration from another GPU generation.

## Follow the matrix tile through the machine

For `X[M,K] W[K,N]`, arithmetic work is `2MKN`. Ignoring reuse outside the kernel, operand traffic is approximately `bytes(X)+bytes(W)+bytes(Y)`. At small M, many weights are read for few output tokens; at large M, each weight tile can serve many rows. A roofline estimate `min(compute_ceiling, bandwidth × arithmetic_intensity)` explains the shift but does not include launch overhead, register spills, or poor tile occupancy.

A tiled CDNA kernel loads operands from HBM, stages data in LDS or registers, feeds Matrix Fused Multiply Add (MFMA) instructions, accumulates, and writes an epilogue. Its lane-to-element mapping must match the instruction and datatype. A 64-thread wavefront does not execute a 32-thread CUDA warp's layout unchanged. Larger tiles increase reuse but consume more registers/LDS and can leave few blocks available when M is tiny.

The current AMD architecture table identifies CDNA3 `gfx942` devices such as MI300X/MI325X with 64-thread wavefronts and 64 KiB LDS, while CDNA4 `gfx950` MI350X/MI355X has 160 KiB LDS and the same wavefront width. More LDS broadens possible staging schedules, but does not make every larger tile faster. Kernel occupancy, per-block allocation, and instruction availability still constrain the schedule.

For example, a projection with `M=4` wastes most rows of a tile designed for `M=128`. A skinny-GEMM or split-K strategy may expose additional parallel work. Split-K also creates partial-output reduction and extra traffic; at a larger M it can lose to an ordinary GEMM. MoE adds another dimension: total tokens are not tokens per expert, so an apparently large batch can still contain many tiny expert GEMMs.

## What upstream already supplies

AMD's current vLLM guide documents AITER linear and skinny-GEMM paths, hipBLASLt selection, FP8 padding, and CDNA4 FP4 assembly GEMM. The FP4 assembly path specifically requires MI350X/MI355X with MXFP4 weights; it is not a CDNA3 FP4 recommendation. AITER already ships operator implementations, model/architecture tuning configurations, and GEMM/MoE test entry points. Recreating these dispatches is not a useful candidate.

The checked vLLM MXFP4 implementation also contains backend-specific format conversion and an explicit gfx942 groupwise-int4 conversion path. That is a different execution representation from native CDNA4 MXFP4 arithmetic. Comparing them only by “four-bit weights” hides the conversion and kernel differences.

Remaining gains can come from missing production shapes, scale/weight layout alignment, padding waste, and a better choice among existing kernels. BF16, FP16, FP8, and MXFP4 need separate shape tables. A tuned result for one architecture, expert width, or quantization grouping should not be promoted to a universal ROCm default.

## Distinguish shape tuning from service gains

Use AITER's existing `op_tests/test_gemm_a8w8.py` and `test_moe.py` as entry points, adapting their inputs to actual model shapes and retaining the owning library's measurement procedure. Compare the current selected kernel with another supported schedule. Inspect instruction utilization, LDS/register pressure, spills, launch count, padding, and output error. Include uneven expert token counts rather than only uniform synthetic batches.

Then measure low-load decode and mixed prefill/decode service workloads. Observe TTFT, TPOT, successful throughput, and memory headroom. If GEMM improves but latency does not, check attention, launch gaps, and collectives before adding more tuning dimensions.
## Sources

Checked 2026-10-14; identities are in the [category index](README.md).

- [AMD architecture specifications](https://rocm.docs.amd.com/en/latest/reference/gpu-arch-specs.html).
- [Current vLLM/AITER optimization guide](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/optimization/vllm-v1-optimization.html).
- [AITER at the checked commit](https://github.com/ROCm/aiter/tree/c09dc31787c21cd7fa7acbe4addef256766bd58a).
- [vLLM MXFP4 layout and conversion](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/layers/quantization/mxfp4.py).

[Heterogeneous execution](README.md) · [Kernel design](../kernel-design/README.md) · [Knowledge index](../README.md)
