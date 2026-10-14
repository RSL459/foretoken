<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Kernel Design

English | [简体中文](README_zh.md)

Choose a mechanism from the work that remains expensive in the actual layer, including its inputs, outputs, and concurrent operations.

- [Reuse GEMM setup through persistent tile scheduling](reuse-gemm-setup-through-persistent-tile-scheduling.md): balance tile waves, locality, and overlap when blocks process several outputs.
- [Overlap load, compute, and store through warp specialization](overlap-load-compute-and-store-through-warp-specialization.md): divide loading, matrix computation, and output work without losing occupancy to buffering and synchronization.
- [Reduce intermediate traffic through layout-aware operator fusion](reduce-intermediate-traffic-through-layout-aware-operator-fusion.md): remove intermediate memory traffic while preserving consumers, aliases, and compiler matching.
- [Reduce sampling work through fused radix selection](reduce-sampling-work-through-fused-radix-selection.md): reduce filtering and sampling work without changing the requested distribution.

For model-specific computation, continue to [attention](../attention-state/README.md) or [MoE](../moe-execution/README.md). [Compilation and runtime](../compiler-runtime/README.md) covers graph integration; [heterogeneous hardware](../heterogeneous-hardware/README.md) covers backend-specific execution constraints.

[All inference knowledge](../README.md)
