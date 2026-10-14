<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce multimodal TTFT through adaptive encoder microbatching

English | [简体中文](reduce-multimodal-ttft-through-adaptive-encoder-microbatching_zh.md) | [Multimodal generation](README.md)

## When encoding delays first-token delivery

A fast vision kernel can coexist with poor multimodal TTFT when preprocessing, encoder batch formation, embedding transfer, or decoder readiness dominates the request. Encoder separation is already documented in vLLM. The useful research question is how to overlap these stages without retaining embeddings indefinitely or waiting too long to fill a batch.

EAServe, submitted in September 2026, studies adaptive encoder microbatching alongside its broader disaggregated design. Its microbatch policy dispatches on a full batch, an arrival-rate-derived idle gap, or an oldest-request age limit. The policy illustrates a concrete tension: waiting increases device utilization but consumes the request's first-token budget. A fixed large batch is not automatically suitable for sparse traffic.

## One execution and its ownership

Consider four image requests arriving unevenly. The encoder collects ready processed tensors until its microbatch fills or the idle-gap condition fires. It runs the vision model, associates each output with its request and input-item position, and publishes transfer metadata. The consuming prefill scheduler waits for the required embeddings, schedules a load, and executes text-plus-image prefill only after completion. Meanwhile the encoder can compute another microbatch. Transfer and compute overlap only if the timeline shows them running concurrently, not merely because both APIs are asynchronous.

For V visual tokens, decoder embedding width d, and b bytes per element, an embedding transfer has approximately Vdb payload bytes. At V=4,096, d=3,584, b=2, that is about 28 MiB before metadata and protocol overhead. Reusing a cached embedding may eliminate encoding but still require a transfer to the consuming worker.

Current vLLM's encoder cache manager tracks references by request and input position. Released references make an item reclaimable; the embedding can remain cached until another allocation needs space. Eviction notifications exclude entries reused later in the same scheduling pass. These distinctions prevent a logical release from becoming premature physical deletion. Cancellation must also remove request references and terminate or complete owned transfers before buffers are reused.

## Conditions and implementation state

Use released VLM weights and their processor; the batching method requires no new training. vLLM's documented examples include Qwen2.5-VL, ExampleConnector, and ECMooncakeConnector. The latter uses Mooncake TransferEngine with TCP or RDMA where available. The audio path has model-specific token-length metadata and covers standalone audio, not video carrying an audio track. Example proxy routes are not a complete realtime API.

EAServe reports an implementation using NIXL, libsmctrl, CUDA, and configuration search on NVIDIA GPUs, but its paper does not identify a public author code repository. Its queueing policy can motivate an experiment; it is not a ready-to-enable upstream switch. FP16/BF16 embedding transfer preserves the chosen representation if no extra conversion is introduced. Backend portability, encoder graph shapes, and altered encoder weights still require separate checks.

## A discriminating service experiment

Replay the same images and arrival timestamps through immediate dispatch, fixed microbatch waiting, and adaptive idle-gap dispatch. Vary item sizes and request image counts independently of arrival rate. Keep stage placement, checkpoint, dtype, transfer transport, and decoder configuration fixed, so a result cannot be attributed to a different resource allocation.

Measure preprocessing completion, encoder queue wait, encode duration, transfer completion, decoder wait, TTFT tails, device utilization, transferred bytes, peak live embedding memory, and SLO-compliant successful requests. Include cancellations while queued, during encoding, and during transfer; observe whether memory returns to its expected steady state. Do not count canceled requests as completed goodput.

If bigger batches reduce encode time per image but worsen TTFT, waiting dominates. If adaptive dispatch improves only steady Poisson arrivals but not bursts, test the estimator's response time rather than claiming a universally better batch size. The remaining question is how arrival-aware execution balances embedding lifetime and handoff costs.

## References

- [EAServe, arXiv:2609.31551v1](https://arxiv.org/html/2609.31551v1): September 2026 microbatch and transfer method; public author code not identified.
- [vLLM encoder disaggregation](https://docs.vllm.ai/en/latest/features/disagg_encoder/): current flow, connectors, examples, and audio restrictions.
- [Encoder-cache manager at `6849ca6`](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/encoder_cache_manager.py): embedding lifetime and eviction; commit dated 2026-10-13.
