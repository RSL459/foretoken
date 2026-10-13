<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Custom Operator Boundaries and Compiler Visibility

English | [简体中文](custom-operator-boundaries_zh.md)

Use this when a fast standalone kernel fails to improve a compiled model, graph breaks multiply around it, or a compiler pass no longer recognizes the computation.

## A kernel is also a compiler interface

A registered custom operator supplies an argument schema, dispatch implementations, and a metadata-only FakeTensor implementation. The latter describes output shapes, dtype, device, and relevant layout relationships without executing the real arithmetic. Mutation and aliasing declarations tell the compiler which values can change.

The compiler can trace that call while treating its native implementation as opaque. This avoids tracing complex device or host logic, but also hides opportunities to fuse neighboring operations. Registering an operator therefore makes it usable in a compiled graph; it does not make its internal implementation visible to the optimizer.

Current PyTorch supports these contracts directly. vLLM already uses custom attention operations and explicit compilation/fusion passes. A new operator should fit that existing boundary rather than introduce a second tracing or dispatch layer.

## Follow a replacement through the graph

Consider replacing `normalization → conversion → projection` with a native operation. A FakeTensor function returning a contiguous output when the real kernel returns a strided view can make downstream layout assumptions wrong. Declaring the operation pure while it writes an input can allow invalid reuse or reordering. Even correct metadata can prevent fusion that previously combined conversion with the projection.

There are three distinct design choices:

- Keep operations visible as tensor expressions so the compiler can transform them.
- Use an opaque kernel for a complete responsibility where hand-designed scheduling matters.
- Teach an existing compiler pass to recognize a supported pattern and replace it with that kernel.

The third is already used by vLLM's Q/K normalization/RoPE fusion. Its value depends on matching the actual model graph and preserving packed-buffer semantics, not merely registering a new function name.

## Capture safety is separate from tracing

An opaque custom operation may still perform a CPU copy, read a device scalar on the host, or use unsupported allocation behavior. Successful Dynamo tracing is not proof of CUDA Graph safety. PyTorch's CUDA Graph documentation describes an unsafe-operation tag and partitioning that can isolate unsupported operations. Those mechanisms already exist; the design choice is where to put the boundary and what performance it costs.

For stateful inference kernels, describe cache writes and input/output aliases explicitly. The owner of cache lifetime must remain the engine. A local operator should not silently retain per-request buffers or create a competing state lifecycle.

## Experiment

Compare three complete paths when relevant: the existing visible expression, the opaque replacement, and a pattern-selected replacement. Inspect graph partitions, inserted copies, generated kernels, and actual dispatch. Preserve real strides and mutations in the numerical comparison, including repeated steps and another consumer retaining the input.

PyTorch's `opcheck` can check registration integration; it does not establish the mathematical correctness of a custom algorithm. Use the existing model/reference comparison for that responsibility. For an inference-only kernel, training-gradient support is only relevant if the intended consumer needs it.

Measure full-layer and serving performance after warmup, plus any new compilation/startup cost. A microkernel gain accompanied by another materialization or graph break may be a net loss.

## Sources and implementation state

Checked 2026-10-14.

- [PyTorch custom C++/CUDA operator tutorial](https://docs.pytorch.org/tutorials/advanced/cpp_custom_ops.html): schema, FakeTensor, mutation, and registration checks.
- [vLLM v0.31.0 compilation design](https://docs.vllm.ai/en/v0.31.0/design/torch_compile/): attention boundaries and piecewise compilation.
- [Existing QK fusion pass](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/compilation/passes/fusion/qk_norm_rope_fusion.py).
- [PyTorch v2.14 graph partitioning and unsafe custom operators](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md).
