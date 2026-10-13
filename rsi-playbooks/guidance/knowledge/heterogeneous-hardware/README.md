<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Heterogeneous execution

English | [简体中文](README_zh.md)

Compare execution mechanisms rather than vendor feature lists. These entries cover local compute, memory movement, and communication constraints; cluster scheduling and deployment ownership remain outside their scope.

- GEMM tuning stops fitting another AMD generation or batch: [CDNA shapes, layouts, and matrix throughput](cdna-shapes-and-layouts.md).
- CUDA-like APIs do not preserve quantized fusion: [MetaX quantized stage boundaries](metax-native-quantized-fusion.md).
- Graph replay and auxiliary streams change latency or progress: [graph and stream portability](graph-stream-portability.md).
- Faster communication does not accelerate the model: [collectives on the critical path](collective-critical-path.md).
- Decide when offload or unequal devices help: [CPU/GPU placement and transfer budgets](cpu-gpu-placement.md).

See [quantization](../quantization/README.md), [kernel design](../kernel-design/README.md), [compiler/runtime](../compiler-runtime/README.md), and [parallelism/communication](../parallelism-communication/README.md) for their respective mechanisms. Return to the [knowledge index](../README.md).

## Evidence scope

Official documentation and current source were checked on 2026-10-14. Snapshots: vLLM `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`, AITER `c09dc31787c21cd7fa7acbe4addef256766bd58a`, ROCm systems `f1b316f12c75430787032e99405834f59a026ae1`, MetaX vLLM `cec91763dbe968fe4478fc066f57ecf5877c3965`, and llama.cpp `77c4540ce4667f4577753fe034a3a8042f510b8f`; each head is dated 2026-10-13. MetaX mcoplib head `f325795aac1ee71cd51111b065f6dd175246961d` is dated 2026-10-08. A head snapshot establishes source availability, not binary compatibility across releases.
