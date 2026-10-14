<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Heterogeneous execution

English | [简体中文](README_zh.md)

Device instruction layouts, memory movement, stream dependencies, and collective implementations determine how the same model executes on different hardware.

- GEMM tuning stops fitting another AMD generation or batch: [CDNA shapes, layouts, and matrix throughput](cdna-shapes-and-layouts.md).
- CUDA-like APIs do not preserve quantized fusion: [MetaX quantized stage boundaries](metax-native-quantized-fusion.md).
- Graph replay and auxiliary streams change latency or progress: [graph and stream portability](graph-stream-portability.md).
- Faster communication does not accelerate the model: [collectives on the critical path](collective-critical-path.md).
- Decide when offload or unequal devices help: [CPU/GPU placement and transfer budgets](cpu-gpu-placement.md).

See [quantization](../quantization/README.md), [kernel design](../kernel-design/README.md), [compiler/runtime](../compiler-runtime/README.md), and [parallelism/communication](../parallelism-communication/README.md) for their respective mechanisms. Return to the [knowledge index](../README.md).
