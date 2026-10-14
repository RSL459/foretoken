<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Dynamic Shapes and Profitable Specialization

English | [简体中文](dynamic-shape-specialization_zh.md)

Variable serving batches can cause repeated compilation, while broad symbolic kernels may underperform on common shapes. Specialization trades startup cost for steady-state savings.

## Symbolic compilation and graph replay solve different problems

A symbolic compiled kernel can accept a varying dimension without recompilation. CUDA Graph replay usually still needs a fixed captured execution shape. One symbolic Inductor graph may therefore correspond to several CUDA Graph recordings. Treating these caches as the same thing hides whether time is spent compiling code, capturing graphs, or padding execution.

PyTorch v2.14 documents automatic dynamism: initial compilation assumes static input sizes; after a size-triggered recompile, changed dimensions can become dynamic. Explicit input annotations can avoid that first unnecessary specialization. The documentation recommends targeted annotations rather than making every size and integer dynamic indiscriminately.

vLLM already provides its own compilation integration and optional static `compile_sizes`. Research should begin at that owner, not by wrapping the whole serving application in another `torch.compile` call.

## Why dynamic inputs can still specialize

Suppose a model path chooses a different operation when token count is one, below a threshold, or above it. Symbolic execution traces the selected branch and records conditions under which it remains valid. A later shape crossing that condition can require another graph. Dynamic dimensions do not remove algorithmic branches.

The same issue appears when a Triton kernel uses a varying value as `constexpr`, or a custom operation's metadata implementation turns a symbolic dimension into a concrete integer. Making the outer tensor dimension dynamic does not repair that inner specialization boundary.

A useful design distinguishes dimensions that change frequently from stable parameters such as head size or matrix width. Stable quantities enable strong specialization. Frequently changing token counts can use symbolic code, a small set of common specializations, or padded graph buckets. Each choice moves cost among startup, code quality, padding, and memory.

## Decide whether specialization pays

For a particular shape, let `C` be the extra compile/capture cost and `Δt` the measured per-use saving over the generic path. Ignoring memory and contention, at least `C/Δt` uses are needed to amortize the specialization. The relevant frequency comes from real engine steps over the worker's lifetime, not a benchmark loop that repeats one shape forever.

Separate an intentional shape-dependent algorithm from an accidental guard. Removing a meaningful branch may degrade the fast path. Conversely, preserving a Python branch that selects equivalent layouts can create avoidable graph proliferation. Inspect guard and generated-code evidence before deciding which case applies.

## Experiment

Replay a representative sequence of batch shapes in a fresh process and then in a warmed process. Record compilation events, graph captures, generated variants, memory, and step time. Compare the generic path with a few frequent static shapes, keeping operator/backend selection fixed where possible.

Exercise threshold crossings, empty or singleton dimensions where supported, and the largest task shape. Inspect compiler guard diagnostics and generated kernels to locate specialization. Finally measure deployment readiness and steady-state service behavior separately: a short-lived worker can favor a different compilation policy from a long-lived replica.

## Sources and implementation state

Checked 2026-10-14.

- [PyTorch v2.14 dynamic-shape documentation](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_dynamic_shapes.md): automatic dynamism, targeted annotations, and specialization semantics.
- [vLLM v0.31.0 compilation integration](https://docs.vllm.ai/en/v0.31.0/design/torch_compile/): symbolic token dimension, optional static compilation sizes, and artifact reuse.
- [PyTorch v2.14 CUDA Graph Trees](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md): separate recordings for concrete execution shapes. See also [graph buckets](graph-buckets-and-dispatch.md).
