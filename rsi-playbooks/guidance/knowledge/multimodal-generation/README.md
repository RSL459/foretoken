<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Multimodal generation

English | [简体中文](README_zh.md) | [Inference knowledge](../README.md)

Choose the entry matching the work that delays the first usable output or limits quality-qualified throughput.

- [Why does the same image still require expensive prefill?](visual-token-cache.md) Distinguish exact encoder reuse from VLCache's approximate cross-context vision KV reuse, and account for dynamic visual token counts.
- [Why is first-token latency high when the encoder kernel is fast?](encoder-pipeline-cache.md) Analyze encoder microbatch waiting, embedding lifetime, transfer completion, and execution overlap; EAServe supplies a recent adaptive batching reference.
- [What should be cached between diffusion steps?](diffusion-feature-cache.md) Compare residual reuse, feature forecasting, and AutoTarget's solver-aware targets, particularly under few-step and nonuniform schedules.
- [When does fewer-step generation mean a different model?](few-step-distillation.md) Trace consistency and causal distillation, checkpoint availability, and long-horizon quality separately from execution speedups.
- [Why do early media tokens not produce early playback?](streaming-audio-video.md) Follow codec chunks, lookahead, waveform/video decoding, transport, and client buffering.
- [Why do mixed resolutions or adapters break efficient batching?](heterogeneous-batching.md) Separate shape packing from compatibility-aware scheduling and pipeline-specific step contracts.

The entries combine current public implementations with remaining research questions. Older papers establish mechanisms; their ordinary implemented capabilities are not listed as new candidates. Source dates and implementation revisions are recorded per entry, with a research cutoff of 2026-10-14. Audio/video generation is external research, not a Foretoken support claim. Numerical examples explain shapes or execution, not measured Foretoken gains.
