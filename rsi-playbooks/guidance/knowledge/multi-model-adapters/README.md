<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Multiple models and adapters

English | [简体中文](README_zh.md) | [Inference knowledge](../README.md)

Start from the sharing boundary: LoRA adapters share a base model's computation, while distinct full models primarily share device capacity and execution time.

- [Why are small-rank updates or packed QKV still slow?](grouped-lora-kernels.md) Examine current grouped shrink/expand kernels, ragged launch grids, and the open split-K proposal with its precision and hardware constraints.
- [Why does total throughput improve while some tenants miss deadlines?](tenant-aware-scheduling.md) Compare rank-aware placement, multi-SLO slack scheduling, and base/LoRA overlap without confusing token generation with release.
- [Why do adapter misses suddenly amplify tail latency?](elastic-adapter-residency.md) Follow device slot lifetime, hot switching, KV competition, and CLIMB's residency-aware ingress, including the public artifact's execution gaps.
- [Why does one idle model prevent another from using memory?](shared-model-execution.md) Study Prism's OSDI 2026 memory ballooning, current kvcached support, and model activation interference; full models do not share KV semantics or a base GEMM merely by colocating.

Current multi-LoRA batching, loading, and elastic-memory facilities are starting points, not new feature proposals. Each entry identifies recent research or a concrete remaining execution question, weights and implementation availability, and a service experiment that can distinguish its cause. Sources are checked through 2026-10-14.
