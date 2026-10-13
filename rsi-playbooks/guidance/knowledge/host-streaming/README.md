<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Host and Streaming Paths

English | [简体中文](README_zh.md)

Follow the work between request arrival, device submission, token decoding, and client delivery. A fast model kernel can expose bottlenecks at any of these boundaries.

- [Host/device scheduling](host-device-scheduling.md): distinguish GIL contention, event-loop blocking, executor queues, and true next-step dependencies.
- [Incremental text decoding](incremental-text-streaming.md): understand Unicode, stop buffering, retained history, and the latency cost of larger chunks.
- [HTTP backpressure and cancellation](http-backpressure-cancellation.md): trace pressure and aborts through queues to engine work and resource release.
- [NUMA and multi-rank host pipelines](numa-rank-host-pipelines.md): separate CPU quota, affinity, allocation locality, and collective arrival skew.

For captured execution, see [compilation and runtime](../compiler-runtime/README.md). For interpreting received chunks and traces, see [measurement and simulation](../measurement-simulation/README.md).

[All inference knowledge](../README.md)
