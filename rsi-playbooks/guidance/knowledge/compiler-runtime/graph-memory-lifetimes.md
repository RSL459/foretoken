<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Graph Memory Lifetimes and Stateful Replay

English | [简体中文](graph-memory-lifetimes_zh.md)

Use this when graph capture consumes too much memory, outputs become invalid across model steps, or state mutation prevents a captured fast path.

## Stable addresses are not stable values

CUDA Graph replay reuses captured addresses. Data at those addresses can change, but moving or replacing an allocation does not update captured pointers: replay still accesses the original addresses. This distinction is central to serving: input tokens change every step, whereas graph buffers, weights, and many cache allocations are expected to remain stable.

PyTorch's current CUDA Graph Trees share a graph-aware memory pool across recordings. They track live outputs and allocation patterns so compatible paths can reuse memory. This is existing runtime functionality; a new inference optimization should first use the engine's allocator and graph wrappers rather than construct another pool manager.

## Why branches affect memory reuse

Consider execution paths `A → B → D` and `A → C → D`. After replaying A, its output is live, but replay has not updated the ordinary allocator as eager execution would. Before recording the new C path, the runtime restores the allocation accounting needed to protect A's output. D may then require another recording because its input address differs from the B path.

Consequently, the number of recordings depends on execution paths and tensor lifetimes as well as shapes. Retaining a tensor for diagnostics, a second consumer, or a future request can change reuse. A pool that was sufficient for a single-path microbenchmark may grow or stop replaying efficiently in the integrated service.

## Mutation and cross-step ownership

PyTorch distinguishes stable parameters/buffers, previous graph outputs, and ordinary eager inputs. An eager input may be copied to a static staging address before replay. Mutating that staging tensor does not automatically update the original eager tensor. Graph-managed outputs and stable buffers have different possibilities because their addresses are already controlled.

Similarly, a model output retained across iterations can be overwritten by a later replay if the runtime regards the previous iteration as finished. PyTorch documents step markers and cloning strategies; v2.14 also documents opt-in cloning of live user-visible output storages. Those facilities do not make arbitrary internal recurrent state or KV storage disposable.

For a stateful serving path, determine who owns each persistent tensor and how the next step obtains it. A full-state clone every token may fix an ownership mistake while introducing substantial memory traffic. Prefer making the actual state lifecycle compatible with the existing runtime; account separately for snapshots required by cancellation or speculative rollback.

## Performance consequences

Separate eager and captured pools can duplicate memory requirements. More graph shapes or paths can retain more buffers, reducing KV capacity. Conversely, aggressive reuse can force copies for consumers that need values after replay. Evaluate memory saved against extra transfer and synchronization, rather than treating lower allocated bytes as sufficient evidence.

## Experiment

Use a repeated-step sequence with changing batch composition and at least one output retained until after the next step. Compare state/output agreement with eager execution and observe allocator peaks after warmup, after a new path, and after returning to an old path. Include actual cancellation or rollback only when the modified responsibility supports them.

Measure any staging or cloning cost separately, then run the service at the same model and context limits. Report graph memory, usable KV capacity, preemption, and tail latency together. The useful outcome is more effective serving capacity without changing state semantics.

## Sources and implementation state

Checked 2026-10-14.

- [PyTorch v2.14 CUDA Graph Trees](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md): pool checkpoints, mutation cases, lifetime constraints, and user-visible output cloning.
- [vLLM v0.31.0 CUDA Graph design](https://docs.vllm.ai/en/v0.31.0/design/cuda_graphs/): engine-owned wrappers and dispatch.
- [Graph buckets](graph-buckets-and-dispatch.md) discusses capture coverage; [attention and recurrent state](../attention-state/README.md) covers the model-specific state that must survive between steps.
