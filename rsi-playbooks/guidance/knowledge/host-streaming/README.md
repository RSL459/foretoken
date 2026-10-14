<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Host and Streaming Paths

English | [简体中文](README_zh.md)

Follow the work between request arrival, device submission, token decoding, and client delivery. A fast model kernel can expose bottlenecks at any of these boundaries.

- [Reduce device idle gaps through host/device execution overlap](reduce-device-idle-gaps-through-host-device-execution-overlap.md): distinguish GIL contention, event-loop blocking, executor queues, and true next-step dependencies.
- [Reduce stream-rendering work through incremental text decoding](reduce-stream-rendering-work-through-incremental-text-decoding.md): understand Unicode, stop buffering, retained history, and the latency cost of larger chunks.
- [Bound stream resource use through backpressure and cancellation](bound-stream-resource-use-through-backpressure-and-cancellation.md): trace pressure and aborts through queues to engine work and resource release.
- [Reduce rank stalls through NUMA-aware host placement](reduce-rank-stalls-through-numa-aware-host-placement.md): separate CPU quota, affinity, allocation locality, and collective arrival skew.

For captured execution, see [compilation and runtime](../compiler-runtime/README.md). For interpreting received chunks and traces, see [measurement and simulation](../measurement-simulation/README.md).

[All inference knowledge](../README.md)
