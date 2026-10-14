<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce MetaX INT8 Traffic Through Compatible Stage Fusion

English | [简体中文](reduce-metax-int8-traffic-through-compatible-stage-fusion_zh.md)

On MetaX MACA, quantization, native GEMM, activation, and communication use backend-specific kernels and workspaces behind CUDA-like model execution interfaces. Fusion depends on the actual boundaries between these stages.

## Dense INT8 has a concrete existing path

The cited MetaX plugin registers `MctlassScaledMMLinearKernel` for the out-of-tree platform's INT8 linear dispatch. Its forward path obtains quantized weights and scales, makes the input contiguous, applies `scaled_int8_quant`, and invokes MetaX's scaled matrix-multiplication wrapper. Dynamic input scales are computed from the input; static input scales are supplied by the layer. A zero-point-aware variant handles asymmetric activation adjustment when required.

For symmetric quantization, a simplified output is

```text
Y[m,n] ≈ s_x[m] s_w[n] Σ_k q_x[m,k] q_w[n,k] + bias[n].
```

Dynamic per-token scaling requires a reduction over K for each token before the GEMM can consume `q_x`. A two-stage implementation may read BF16 input, write INT8 input plus scales, then read those again. A fused producer can avoid materializing some intermediates, but only if its output layout and scale granularity match the native consumer. Eliminating a launch without eliminating traffic or preserving enough parallelism may not help.

For example, an RMSNorm-plus-quantization producer could reuse values already read for normalization. Its consumer must still accept the resulting contiguous or packed INT8 layout. If the normalized dimension is split across tensor-parallel shards, RMSNorm requires a cross-shard sum of squares. A local fused producer must preserve that reduction before applying normalization and quantization.

## MoE is not just the dense path repeated

At MetaX plugin commit `cec91763dbe968fe4478fc066f57ecf5877c3965`, the compressed-tensors INT8 MoE method requires channelwise weights and dynamic per-token inputs. It obtains quantized expert configuration, builds a modular kernel, and applies that kernel with routing tables and shared-expert inputs. The current INT8 oracle prioritizes Triton, batched Triton, and batched DeepGEMM subject to supported-config checks. The selected expert kernel determines GEMM execution and activation layout.

The distinction matters when studying gate/up GEMM, SiLU-and-multiply, requantization, down GEMM, routing-weight application, and combine. A dense fusion that works on `[M,K]` may not fit a batched expert activation format. Routing order, padding, and per-expert token counts affect scale placement and intermediate size. Consult the actually selected path rather than generalizing from an older plugin release or a kernel with a similar name.

## Remaining optimization space

Native INT8 dispatch and modular MoE integration already exist. Possible gains concern avoidable contiguous copies, compatible producer/quantizer fusion, repeated intermediate reads, padding, and workspace lifetime. FP8 or MXFP8 support must be traced independently; an INT8 wrapper is not evidence for NVFP4 or MXFP4 arithmetic on a particular MetaX device.

Use a matching released vLLM/plugin/SDK/operator-library combination for experiments. The plugin README describes master as following upstream, with supported component combinations documented for releases.

## A focused comparison

Capture one real dense projection and one routed-expert stage, preserving dtype, strides, scale shapes, expert token distribution, and current stream. Compare the existing stage against one compatible fusion. Measure quantization, copies, GEMM, activation, and combine separately and together; inspect allocated intermediates and numerical error. Include tiny decode and large prefill shapes.

Compare uniform and real expert-token distributions to determine whether fusion gains survive routing imbalance.

## References

- [MetaX dense INT8 registration and execution](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/registry/linear_kernels/int8.py).
- [Current compressed-tensors INT8 MoE method](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/registry/quant_config/compressed_tensors_moe/compressed_tensors_moe_w8a8_int8.py).
- [Current INT8 MoE oracle](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/model_executor/layers/fused_moe/oracle/int8.py) and [release compatibility guidance](https://github.com/MetaX-MACA/vLLM-metax).

[Heterogeneous execution](README.md) · [Quantization](../quantization/README.md) · [Knowledge index](../README.md)
