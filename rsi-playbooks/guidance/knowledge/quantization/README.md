<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Quantization

English | [简体中文](README_zh.md)

Choose a representation, calibration procedure, and executable kernel together. These notes cover weights and activations; cache representation belongs to [KV caching](../kv-cache/README.md).

- Smaller checkpoints without faster inference: [Match low-bit formats to executable kernel layouts](match-low-bit-formats-to-executable-kernel-layouts.md).
- Maximum-based scaling loses important information: [Reduce quantization error with activation-aware block scales](reduce-quantization-error-with-activation-aware-block-scales.md).
- Redistribute outliers without changing the model function: [Reduce quantization outliers through coordinate rotation](reduce-quantization-outliers-through-coordinate-rotation.md).
- Decide whether extra calibration or training is worthwhile: [Recover quantized quality through rounding and scale learning](recover-quantized-quality-through-rounding-and-scale-learning.md).
- Choose layers that need higher precision: [Balance mixed-precision quality, memory, and kernel cost](balance-mixed-precision-quality-memory-and-kernel-cost.md).

Research choices include workload-specific calibration, quality recovery, representation/layout alignment, and measured format selection. See [heterogeneous execution](../heterogeneous-hardware/README.md) for hardware-specific consequences and the [knowledge index](../README.md) for other topics.

## References

Implementation sources: [vLLM `6849ca69`](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9), [llm-compressor `990fdd2f`](https://github.com/vllm-project/llm-compressor/tree/990fdd2fb41af48f105dbdebd088a96b627701b1), and [NVIDIA Model Optimizer `b5f10f8b`](https://github.com/NVIDIA/Model-Optimizer/tree/b5f10f8bf96201241c35b86498557bd6fdde10ca).
