<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# CUDA Graph Buckets and Runtime Dispatch

English | [简体中文](graph-buckets-and-dispatch_zh.md)

## Graph coverage is a workload property

CUDA Graph replay submits a recorded device execution with fewer host launches. It still executes the recorded work and requires compatible shapes, addresses, and operation behavior. A service therefore captures selected batch configurations and dispatches incoming work to a compatible graph.

In vLLM v0.31.0, the dispatcher maintains registered FULL and PIECEWISE keys. It pads token counts to a capture size, includes request geometry and LoRA state where required, checks FULL first, then PIECEWISE, and otherwise returns NONE. Speculative uniform decode can have more than one query token per request. Token count alone is not a complete compatibility key.

Coverage and cost depend on the workload's batch distribution, attention backend, hybrid layers, and active adapters.

## Padding versus capture cost

Suppose a batch has 17 token positions and the next captured size is 32. The graph may execute substantial work for padded positions, even though those positions produce no requested output. A smaller bucket can reduce this waste but adds capture time and possibly memory. An eager execution avoids padding but incurs more launch overhead.

A useful conceptual objective is the observed average of `execution(padded shape) + dispatch/launch cost`, with startup and capture-memory costs tracked separately. The relevant distribution is that of actual engine steps, not only client concurrency. Mixed prefill/decode, speculative query lengths, and LoRA composition change that distribution.

FULL replay captures the complete eligible execution. PIECEWISE captures compatible regions while unsupported operations execute outside them. In the inspected dispatcher, PIECEWISE keys relax request-count and uniformity fields; FULL keys retain geometry needed by backend metadata. Broadening a key without proving that the captured operation is valid for the new geometry can produce wrong execution.

## Design choices beyond more buckets

Measure why an eager path was selected. It may exceed the capture limit, use an unsupported attention operation, or have a different adapter configuration. Adding token buckets cannot fix a backend's missing capture support. Conversely, making an operation capture-compatible can increase coverage without capturing every possible size.

A whole-graph compiler pass may conflict with piecewise splitting, so compilation and graph mode must be considered together. Hybrid models inherit the restrictions of participating components. Prefer a small, workload-relevant set of supported configurations over indiscriminate capture expansion.

Graph memory also reduces space available to KV caches. A lower launch cost can be offset by additional preemption or fewer concurrent sequences; measure those effects in the serving workload rather than only a replay microbenchmark.

## Experiment

Collect actual step token counts, request counts, decode uniformity, adapter cases, selected mode, and padded sizes. Compare a candidate bucket set against the current one with identical arrivals and outputs. Separate startup/capture duration, steady-state step time, graph memory, KV capacity, and end-to-end tail latency.

For a backend change, test the same batch geometry in eager and replay, including mixed traffic and speculative decoding when applicable. Confirm that output/state agreement holds over repeated steps before attributing service improvements to graph coverage.

## Sources and implementation state

Checked 2026-10-14.

- [vLLM v0.31.0 CUDA Graph design](https://docs.vllm.ai/en/v0.31.0/design/cuda_graphs/): modes and backend capability boundaries.
- [Pinned dispatcher](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/v1/cudagraph_dispatcher.py): padding, LoRA cases, registered keys, and fallback order.
- [PyTorch v2.14 CUDA Graph Trees](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md): shape-specific recordings and memory-lifetime constraints.
