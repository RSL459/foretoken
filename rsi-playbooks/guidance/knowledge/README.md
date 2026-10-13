<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Inference Knowledge

English | [简体中文](README_zh.md)

Find mechanisms, implementation evidence, and research questions for improving an inference system. Start with the observed cost or design decision, then follow the relevant category. Each entry explains how an approach works, where it applies, what upstream already implements, and which experiments can distinguish the remaining choices.

## Model computation

- [Attention and recurrent state](attention-state/README.md): dense attention pipelines, MLA layouts, sparse indexing, channel-gated recurrence, and state reuse.
- [MoE execution](moe-execution/README.md): expert work partitioning, token assignment, replica balancing, and quantized execution layouts.
- [Speculative decoding](speculative-decoding/README.md): draft generation, verification, acceptance cost, adaptive depth, and candidate selection.
- [Quantization](quantization/README.md): block-scaled formats, outliers, calibration, and the interaction between numerical error and available kernels.
- [Multimodal and generative models](multimodal-generation/README.md): visual encoding, multimodal batches, diffusion acceleration, and streaming generation.
- [Multiple models and adapters](multi-model-adapters/README.md): LoRA computation, adapter residency, tenant scheduling, and shared execution capacity.

## Device execution

- [Kernel design](kernel-design/README.md): persistent work assignment, warp-specialized pipelines, layout-aware fusion, and vocabulary selection.
- [Compilation and runtime](compiler-runtime/README.md): shape specialization, graph dispatch, custom operator boundaries, and graph memory lifetimes.
- [Parallelism and communication](parallelism-communication/README.md): tensor, expert, context, and pipeline parallelism; communication granularity and overlap.
- [Heterogeneous hardware](heterogeneous-hardware/README.md): architecture-specific layouts, graph and stream behavior, collectives, and CPU/GPU execution choices.

## Serving and resource management

- [Engine scheduling](engine-scheduling/README.md): token budgets, prefill/decode interference, preemption, fairness, and layer-group prefill.
- [KV caching](kv-cache/README.md): storage tiers, partial reuse, compression, selection, and transfer compatibility.
- [Request routing and admission](routing-admission/README.md): cache affinity versus queueing, predicted work, deadlines, and overload.
- [Disaggregated serving](disaggregated-serving/README.md): P/D and attention/FFN separation, stage balance, transfers, and heterogeneous stage placement.
- [Autoscaling and placement](autoscaling-placement/README.md): capacity estimation, feedback delay, cold starts, topology, and safe capacity removal.
- [Model loading and storage](model-loading-storage/README.md): loading pipelines, I/O and host memory, distributed weights, and sleep/wake recovery.

## Host execution and evidence

- [Host and streaming paths](host-streaming/README.md): host/device scheduling, incremental text, backpressure, cancellation, and NUMA effects.
- [Measurement and simulation](measurement-simulation/README.md): arrivals and queueing, SLO goodput, trace critical paths, simulator calibration, and numerical divergence.

A decode slowdown can involve several categories. For example, use attention or MoE entries to understand computation, communication entries to inspect rank dependencies, and host/runtime entries to explain launch gaps. The categories identify the mechanism's owner; cross-links connect the execution path.

## Reading the evidence

Implementation status is scoped to the cited release, commit, or pull request and its check date. An upstream feature is part of the current comparison, not a new optimization merely because it appears in a paper. Entries identify remaining design questions, including where workload, hardware, or model structure changes the trade-off.

Author measurements retain their original conditions. Foretoken measurements belong to linked experiment records; implementation availability alone establishes neither quality nor a service speedup. Research that needs new weights, training, or model changes is distinguished from an execution-only change.

## Add or update knowledge

Use one category directory per technical responsibility and one descriptive file name per question, with an English file and a `_zh.md` counterpart. Category READMEs link entries by the problem they help solve. An entry can compare several papers or implementations; a project name alone is not a reason to create a new category or another note.

The [knowledge template](../../templates/guidance-template.md) provides a structure for the problem, mechanism, applicability, implementation state, and useful experiments. Extend an existing entry when new evidence changes the same question. Preserve explanations of failed approaches and reusable inputs or code, and update the category index. Research methods themselves belong in [meta-knowledge](../meta-knowledge/README.md); run-specific commands and raw results belong in [experiment records](../../experiment-records.md).
