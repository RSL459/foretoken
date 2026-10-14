<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 量化

[English](README.md) | 简体中文

权重与激活的数值表示、校准方法和执行 kernel 应一起选择。缓存表示另见 [KV 缓存](../kv-cache/README_zh.md)。

- 检查点更小却没有更快：[块缩放格式与 kernel 布局](block-scaled-formats_zh.md)。
- 按最大值缩放丢失重要信息：[根据激活选择块 scale](activation-aware-block-scales_zh.md)。
- 在不改变模型函数的前提下分散离群值：[旋转、离群值与在线开销](rotation-and-outliers_zh.md)。
- 判断是否值得增加离线优化：[学习舍入与 scale 恢复](learned-rounding-and-scale-recovery_zh.md)。
- 选择需要保留更高精度的层：[考虑实际 kernel 成本的混合精度](mixed-precision-kernel-cost_zh.md)。

研究选择包括工作负载匹配、质量恢复、表示与布局协同，以及以实测成本选择格式。硬件约束见[异构执行](../heterogeneous-hardware/README_zh.md)，其他主题见[知识索引](../README_zh.md)。

## 资料范围

核对日期为 2026-10-14，依据以下 2026-10-13 开发快照：[vLLM `6849ca69`](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9)、[llm-compressor `990fdd2f`](https://github.com/vllm-project/llm-compressor/tree/990fdd2fb41af48f105dbdebd088a96b627701b1)、[NVIDIA Model Optimizer `b5f10f8b`](https://github.com/NVIDIA/Model-Optimizer/tree/b5f10f8bf96201241c35b86498557bd6fdde10ca)。
