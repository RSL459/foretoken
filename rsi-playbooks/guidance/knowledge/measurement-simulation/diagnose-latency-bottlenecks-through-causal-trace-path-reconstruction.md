<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Diagnose latency bottlenecks through causal trace-path reconstruction

English | [简体中文](diagnose-latency-bottlenecks-through-causal-trace-path-reconstruction_zh.md) · [Measurement and simulation](README.md) · [Knowledge](../README.md)

## Summed duration is not elapsed latency

A CPU operator can submit an asynchronous device kernel and return before the kernel finishes. Two streams can execute concurrently. A parent span includes its children. A collective can include waiting for another rank. Summing these durations answers neither request latency nor available speedup unless the dependencies are known.

For two intervals A and B, occupied wall time is |A ∪ B| = |A| + |B| − |A ∩ B|. This union removes overlap but still does not describe causality. A long off-path task can occupy resources without delaying the selected request; a short launch or synchronization operation can be critical because all subsequent work depends on it.

## Reconstruct the path to the observed event

Represent operations as vertices with measured durations and dependencies as edges. With sufficient resources, operation v finishes at `c_v = d_v + max_{u→v} c_u`, where d_v is its duration and c_u a predecessor's completion time; a source node finishes at its release time plus d_v. The longest causally required path then determines the selected completion event. Shared-device contention adds scheduling constraints that a simple dependency graph may not capture, so the model must retain which streams and resources actually compete.

Consider 4 ms of compute overlapped with 3 ms of communication, followed by a 1 ms synchronization-dependent stage. The ideal elapsed time is 5 ms, not 8 ms. Shortening communication to 2 ms leaves elapsed time unchanged if compute still dominates. Shortening compute to 2 ms gives 4 ms. This is an illustrative dependency graph; overlapping operations can slow one another through HBM or SM competition, changing both durations.

The target event matters. A critical path to first engine token differs from one to first visible text, last HTTP event, or KV release after cancellation. CPU scheduling after device completion may matter to visible text but not to the model kernel. A profiler focused on model processes can omit frontend parsing, network queues, and client scheduling entirely.

## Distinguish queueing from execution

A kernel's start can lag its host launch because another stream occupies the device or because an event dependency is unresolved. A long host CUDA API interval can indicate synchronization, resource contention, or tracing overhead rather than a slow kernel. Conversely, a short launch followed by an empty device interval can indicate delayed submission elsewhere in the host pipeline.

Across ranks, communication duration needs collective identity, entry times, and preceding work. Early ranks may wait inside the collective for a late rank. Summing every rank's communication time counts the same rendezvous repeatedly and can misdiagnose host descheduling as network transfer. Independent node clocks require synchronization or a shared causal reference before cross-node interval subtraction.

Nested spans require a separate distinction: inclusive duration contains child work, whereas self time excludes it. Even self time can contain blocking waits. A sampled CPU stack estimates where time was spent while sampled, not necessarily which operation delayed the device. The trace must retain enough process, thread, rank, stream, and correlation identity to connect the observations.

## Experiments that test the dependency interpretation

Select a repeated steady-state step and annotate the earliest event that can release its successor. Compare three quantities: operator duration totals, union of device-busy intervals, and step elapsed time. Large totals with a short union indicate overlap or nesting. A small union with a long step indicates uncovered host work, waiting, or missing trace coverage.

Then perturb one stage while holding shapes and workload fixed. If reducing an apparent hotspot does not advance successor start or end-to-end completion, it is hidden, off-path, or compensated by contention. If a host-core change advances device submission without changing kernel durations, the exposed cost belongs to scheduling rather than device execution. These perturbations distinguish critical-path hypotheses more directly than sorting by total operator time.

Capture graph execution at the appropriate granularity. Graph-level tracing reduces overhead but hides internal dependencies; node-level tracing reveals them while potentially disturbing short decode steps. Compare traced and ordinary cadence before trusting fine-grained gaps. Startup, compilation, and graph capture also need separate windows from steady state.

Foretoken's PyTorch, Nsight, and mcTracer captures provide different coverage, not interchangeable time budgets. Use captured process/device metadata and the actual tool backend; unsupported correlation cannot be repaired by summing available events. SQL interval analysis can make overlap reproducible, but temporal proximity alone does not create a dependency edge.

## References

- [Nsight Systems User Guide](https://docs.nvidia.com/nsight-systems/UserGuide/index.html): CPU/CUDA correlation, process scope, graph granularity, overhead, and clock alignment.
- [Perfetto Trace Processor](https://perfetto.dev/docs/analysis/trace-processor): slice timestamps/durations and query processing. Interval queries do not themselves identify causal edges.
- [SGLang overlap utilities](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/overlap_utils.py): explicit publication, device events, asynchronous copies, and consumer fences; revision dated 2026-10-13.
- [Foretoken profiling guide](../../../../benchmarks/docs/profile/README.md): at `e6ae3df6`; capture-engine preparation, retained results, and separate unprofiled performance runs.
