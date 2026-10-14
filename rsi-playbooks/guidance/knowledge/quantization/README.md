<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Quantization

English | [简体中文](README_zh.md)

Choose a representation, calibration procedure, and executable kernel together. These notes cover weights and activations; cache representation belongs to [KV caching](../kv-cache/README.md).

- Smaller checkpoints without faster inference: [block-scaled formats and kernel layouts](block-scaled-formats.md).
- Maximum-based scaling loses important information: [activation-aware block-scale selection](activation-aware-block-scales.md).
- Redistribute outliers without changing the model function: [rotation, outliers, and runtime cost](rotation-and-outliers.md).
- Decide whether extra calibration or training is worthwhile: [learned rounding and scale recovery](learned-rounding-and-scale-recovery.md).
- Choose layers that need higher precision: [mixed precision with executable kernel costs](mixed-precision-kernel-cost.md).

Research choices include workload-specific calibration, quality recovery, representation/layout alignment, and measured format selection. See [heterogeneous execution](../heterogeneous-hardware/README.md) for hardware-specific consequences and the [knowledge index](../README.md) for other topics.

## Evidence scope

Checked 2026-10-14 against development snapshots dated 2026-10-13: [vLLM `6849ca69`](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9), [llm-compressor `990fdd2f`](https://github.com/vllm-project/llm-compressor/tree/990fdd2fb41af48f105dbdebd088a96b627701b1), and [NVIDIA Model Optimizer `b5f10f8b`](https://github.com/NVIDIA/Model-Optimizer/tree/b5f10f8bf96201241c35b86498557bd6fdde10ca).
