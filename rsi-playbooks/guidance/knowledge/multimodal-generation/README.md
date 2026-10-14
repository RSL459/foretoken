<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Multimodal generation

English | [简体中文](README_zh.md) | [Inference knowledge](../README.md)

Choose the entry matching the work that delays the first usable output or limits quality-qualified throughput.

- [Reduce visual prefill through encoder and KV reuse](reduce-visual-prefill-through-encoder-and-kv-reuse.md) Distinguish exact encoder reuse from VLCache's approximate cross-context vision KV reuse, and account for dynamic visual token counts.
- [Reduce multimodal TTFT through adaptive encoder microbatching](reduce-multimodal-ttft-through-adaptive-encoder-microbatching.md) Analyze encoder microbatch waiting, embedding lifetime, transfer completion, and execution overlap; EAServe supplies a recent adaptive batching reference.
- [Reduce diffusion compute through feature and solver-target reuse](reduce-diffusion-compute-through-feature-and-solver-target-reuse.md) Compare residual reuse, feature forecasting, and AutoTarget's solver-aware targets, particularly under few-step and nonuniform schedules.
- [Distill few-step generation through consistency and distribution matching](distill-few-step-generation-through-consistency-and-distribution-matching.md) Trace consistency and causal distillation, checkpoint availability, and long-horizon quality separately from execution speedups.
- [Reduce first-media latency through chunked decoding and delivery](reduce-first-media-latency-through-chunked-decoding-and-delivery.md) Follow codec chunks, lookahead, waveform/video decoding, transport, and client buffering.
- [Reduce multimodal padding and waiting through compatible batching](reduce-multimodal-padding-and-waiting-through-compatible-batching.md) Separate shape packing from compatibility-aware scheduling and pipeline-specific step contracts.
