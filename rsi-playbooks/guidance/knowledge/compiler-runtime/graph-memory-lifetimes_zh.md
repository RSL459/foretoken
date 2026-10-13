<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 图内存生命周期与有状态重放

[English](graph-memory-lifetimes.md) | 简体中文

图捕获占用过多内存、输出跨模型步失效，或状态修改使快路径无法重放时，应检查地址、数据存活时间与生命周期归属。

## 地址稳定不代表数值不变

CUDA Graph 重用捕获时的地址，地址中的数据可以变化，但移动或替换分配不会更新已捕获的地址，重放仍会访问原来的位置。服务每步的输入 token 都在变，而图缓冲区、权重和许多缓存分配需要维持地址稳定。

PyTorch 当前的 CUDA Graph Trees 已能在多个记录间共享感知图执行的内存池，通过跟踪存活输出和分配模式实现兼容路径的复用。这是已有运行时能力。新推理优化应先使用引擎的 allocator 与 graph wrapper，而不是另建一套池管理器。

## 为什么分支会影响内存复用

考虑 `A → B → D` 与 `A → C → D` 两条路径。A 重放后，其输出仍存活，但 replay 不像 eager 那样同步更新普通 allocator。记录新的 C 路径前，运行时需要恢复保护 A 输出所需的分配账目；随后 D 的输入地址可能与 B 路径不同，因此还要重新记录。

所以记录数量不仅取决于形状，也取决于执行路径和张量生命周期。为诊断、第二消费者或后续请求保留一个张量，都可能改变复用方式。单路径微基准中够用的池，接入服务后可能增长或失去高效重放。

## 状态修改与跨步归属

PyTorch 区分地址稳定的参数／buffer、前一个图的输出，以及普通 eager 输入。Eager 输入可能先复制到固定 staging 地址；修改 staging 张量并不自动更新原始输入。图管理输出和稳定 buffer 的地址受控，支持条件不同。

跨迭代保留模型输出也有类似问题：运行时若判断上轮已结束，后一次 replay 可能覆盖原输出。PyTorch 提供 step marker 和 clone 方式，v2.14 还记录了可选的用户可见输出复制能力；这些能力不意味着内部循环状态或 KV 可以随意丢弃。

有状态服务中，应明确每个持久张量由谁拥有、下一步如何取得。每 token 复制完整状态或许能掩盖归属错误，却引入大量访存。优先让真实生命周期适配已有运行时，取消或推测回退所需的快照另行计入成本。

## 性能上的连锁影响

Eager 与 captured pool 分离可能增加内存需求。更多图形状和路径保留更多缓冲区，减少 KV 容量；过于积极的复用，又可能迫使跨步消费者复制数据。应同时比较节省的内存、新增搬运与同步，而不是只看 allocated bytes 降低。

## 实验方式

构造批次组成变化的连续多步执行，并保留至少一个输出直到下一步之后。与 eager 比较状态和输出，观察预热后、进入新路径后、回到旧路径后的内存峰值。仅在被改职责确实涉及取消或回退时，把这些真实路径纳入实验。

单独测 staging 或 clone 的成本，再以相同模型和上下文上限运行服务。一起观察图内存、可用 KV 容量、抢占与尾延迟，判断是否在保持状态语义的同时提高了实际服务容量。

## 来源与实现状态

核对日期：2026-10-14。

- [PyTorch v2.14 CUDA Graph Trees](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md)：池状态恢复、mutation、生命周期与用户输出复制。
- [vLLM v0.31.0 CUDA Graph 设计](https://docs.vllm.ai/en/v0.31.0/design/cuda_graphs/)：引擎管理的 wrapper 与分派。
- [图分桶](graph-buckets-and-dispatch_zh.md)讨论捕获覆盖率；[注意力与循环状态](../attention-state/README_zh.md)讨论必须跨步保留的模型状态。
