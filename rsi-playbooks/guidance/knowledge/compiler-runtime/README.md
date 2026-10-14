<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Compilation and Runtime

English | [简体中文](README_zh.md)

Understand how shape choices, compiler visibility, and memory ownership turn individual kernels into a repeated inference execution.

- [Reduce launch overhead with workload-aware graph bucketing](reduce-launch-overhead-with-workload-aware-graph-bucketing.md): improve replay coverage without excessive padding, capture time, or memory.
- [Balance compilation cost with targeted shape specialization](balance-compilation-cost-with-targeted-shape-specialization.md): choose which dimensions stay symbolic and which frequent shapes justify specialized code.
- [Balance custom kernel control and compiler-visible fusion](balance-custom-kernels-and-compiler-visible-fusion.md): preserve metadata, mutation, and capture semantics while deciding what the compiler can optimize.
- [Reuse graph memory through lifetime-aware pooling](reuse-graph-memory-through-lifetime-aware-pooling.md): reuse pools and outputs across paths without losing state or serving capacity.

See [kernel design](../kernel-design/README.md) for work inside a kernel and [host execution](../host-streaming/README.md) for the submission and streaming paths around it.

[All inference knowledge](../README.md)
