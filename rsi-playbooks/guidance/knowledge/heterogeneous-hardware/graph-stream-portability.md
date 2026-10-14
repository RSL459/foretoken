<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Graph and stream portability

English | [简体中文](graph-stream-portability_zh.md)

Graph replay removes repeated host launch work, while auxiliary streams overlap independent device work. Both rely on execution contracts beyond operator signatures. Moving between CUDA, ROCm, and MACA requires checking capture support, communicator ordering, stream binding, and temporary-buffer ownership rather than merely enabling the same graph mode.

## Replay trades launches for shape and memory constraints

If a forward pass launches `n` small kernels, host-side launch work contributes approximately `n t_launch`. A captured graph can reduce that repeated submission cost. It cannot reduce the kernels' arithmetic by itself. Replay also retains buffers and may pad a real token count M to a captured size G, adding `(G−M)` rows of work.

For example, a nine-token decode batch might reuse a sixteen-token graph. Whether seven padded rows are worthwhile depends on how much launch time disappears and whether the extra GEMM or expert work is cheap. A speculative decode batch has more than one query token per request, so request count alone is not a sufficient graph key.

The current vLLM design already separates compilation and capture, provides full and piecewise modes, and dispatches by batch description and backend capability. `FULL_DECODE_ONLY` avoids prefill graphs; `FULL_AND_PIECEWISE` combines full uniform decode with piecewise execution elsewhere. Missing compatible keys execute eagerly. The target version's configuration determines the default mode.

## Streams and collectives form a dependency graph

Suppose the main stream produces input, an auxiliary stream computes a shared expert, and the main stream later combines that result. Correct execution needs a main-to-aux dependency before input consumption and an aux-to-main dependency before output use. Workspace and output buffers must remain valid through completion. Graph capture adds another lifetime: addresses and dependencies must be legal on subsequent replays, not merely during warmup.

NCCL's current graph documentation requires matching capture participation across ranks and describes mixing captured with ordinary operations. It also documents a deadlock caveat when graphs involving multiple communicators are launched from one thread. This is not proof of identical RCCL or MCCL behavior. A setting supported by one library cannot be transferred by spelling alone to another.

An operator must preserve the caller's stream dependencies, either by using the current stream or by explicitly ordering work on internal streams. Concurrent calls also need separate workspace or serialization: a library-internal static workspace can be overwritten while a previous call still uses it. Buffer reuse must wait for all streams accessing the allocation to complete.

## Current integration and useful remaining work

AMD's vLLM guide already documents graph-mode choices for its attention backends. MetaX uses a vLLM hardware plugin, with version-specific native libraries and communicator overrides. The checked MetaX communicator deliberately routes MACA all-gather through the base process-group path. A graph/capture claim must cover that actual call path, not only a directly invoked communication wrapper.

The remaining optimization problem is choosing capture sizes and supported overlap for real shapes while preserving progress. This applies to BF16 and quantized models, particularly hybrid attention, MoE shared experts, and speculative decode. More capture is not automatically better: memory consumed by graphs can reduce serving capacity, and a slow eager segment can dominate despite a fast replay elsewhere.

## A revealing experiment

Use the engine's existing graph dispatcher and the same operator/backend combination. Compare eager, decode-only capture, and the supported mixed mode. Locally inspect warmup versus replay, launch gaps, padding work, allocated memory, current streams, and completion events. Exercise unequal per-rank token counts and mixed prefill/decode rather than only repeated identical batches.

Measure the complete service without profiling overhead, observing TTFT, TPOT, successful outputs, long-run progress, and memory headroom. If overlap fails, preserve communicator identities and device completion boundaries before altering synchronization. A globally synchronized microbenchmark can conceal the ordering problem it was meant to reproduce.

## Sources

Checked 2026-10-14.

- [vLLM graph design at the checked commit](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/design/cuda_graphs.md).
- [NCCL graph contracts](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/cudagraph.html).
- [AMD graph choices](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/optimization/vllm-v1-optimization.html).
- [MetaX communicator implementation](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/distributed/device_communicators/cuda_communicator.py).

[Heterogeneous execution](README.md) · [Compiler/runtime](../compiler-runtime/README.md) · [Knowledge index](../README.md)
