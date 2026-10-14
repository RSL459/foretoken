<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce first-media latency through chunked decoding and delivery

English | [简体中文](reduce-first-media-latency-through-chunked-decoding-and-delivery_zh.md) | [Multimodal generation](README.md)

## What the client is waiting for

Streaming text tokens does not automatically give streaming speech or video. A speech codec decoder may need future codes; a video VAE may wait for a latent chunk; transport may deliver bytes that cannot yet be played. The relevant objective is time to first usable media and sustained delivery without underruns.

Qwen2.5-Omni supplies an architectural foundation: Thinker emits text and hidden-state conditioning, Talker emits speech codes, and a chunked waveform path converts them to audio. Current vLLM-Omni documents an asynchronous Qwen3-Omni Thinker→Talker→Code2Wav pipeline and a separate diffusion-video WebSocket API. These are different model and protocol paths; their capabilities should not be collapsed into a generic “realtime multimodal” label.

## One chunk through the pipeline

Thinker processes the input and provides the information Talker needs to begin. Talker generates a codec chunk before finishing the complete answer. The connector transfers that chunk with request correlation and ordering metadata. Code2Wav decodes it while Talker generates subsequent chunks. The orchestrator owns cancellation and output ordering across stages.

In the Qwen2.5-Omni report, waveform decoding uses a flow-matching DiT and modified BigVGAN. The DiT's chunk receptive field includes two history blocks, the current block, and one future block. Thus the earliest playable chunk waits for lookahead as well as computation. This older model-specific detail should not be assumed to describe Qwen3-Omni's exact codec architecture.

For video output, the cited Omni API sends a `video.chunk_metadata` JSON message immediately followed by a binary frame containing fragmented MP4 bytes. Receive order is part of the delivery contract. The endpoint is `WS /v1/realtime/video`; it generates video output rather than accepting live conversational video. Its documented format is `m4s`, and the pipeline must support step execution and chunk emission. Merely turning on a streaming flag does not make a final-only model incremental.

A simple playback relation helps: if a chunk contains D seconds of media and arrives every A seconds after startup, A≤D is necessary on average for sustained playback, and A<D leaves room to refill the buffer after delays; tail gaps can still exhaust it. Startup latency and long-gap probability therefore matter separately from average generation speed.

## Weights, state, and quality

Use the released model-specific text, speech-code, waveform, or video components as one compatible checkpoint bundle. The Qwen report links release sites; the exact files and Omni model support must be checked for the chosen revision. Chunk streaming itself does not train new weights. Causal video distillation is a different model change described in [few-step distillation](distill-few-step-generation-through-consistency-and-distribution-matching.md).

BF16/FP16 transformer support does not imply identical precision for a vocoder or VAE. CUDA attention, codec, and VAE dependencies determine actual hardware coverage. Smaller chunks may reduce first-media latency while increasing boundary overhead or weakening continuity. Decreasing lookahead, quantizing history, or truncating context changes quality; those are not merely transport optimizations.

Keep request state bounded by consumer progress. A slow or disconnected client can leave generated chunks queued even when GPU execution is healthy. The architecture source establishes synchronization and cancellation but does not specify a universal credit-based backpressure algorithm; any such policy is a research choice to measure, not an existing guarantee.

## Experiments and remaining work

Replay identical prompts with several supported chunk sizes and fixed model, precision, and sampling settings. Compare final-only delivery with genuine incremental decoding, then introduce controlled client delays and cancellation. Test long speech and video runs; short demos miss queue growth and drift.

Measure first codec token, first decoded waveform/frame, first playable client media, inter-chunk P50/P95/P99 gaps, real-time factor, underrun duration, queued bytes, GPU memory, cancellation cleanup time, and accepted media-seconds per second. Speech evaluation should include intelligibility, speaker consistency, and chunk-boundary artifacts; video evaluation should include motion and identity continuity.

If early codec tokens do not improve first playable media, inspect decoder lookahead or packaging. If average real-time factor improves but underruns increase, bursty delivery defeated playback. Remaining opportunities concern chunk-level overlap, buffer control, and quality-preserving operating points.

## References

- [Qwen2.5-Omni report, arXiv:2503.20215v1](https://arxiv.org/html/2503.20215v1): speech architecture and block lookahead; video is input, not generated output in this report.
- [Omni architecture](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/design/architecture_overview.md) and [video API](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/serving/streaming_video_output_api.md): contents at `37f094a`, dated 2026-10-13. These are implemented upstream paths with model-specific restrictions; release `v0.30.0` predates this main revision.
