<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Heterogeneous shapes and multimodal batch compatibility

English | [简体中文](heterogeneous-batching_zh.md) | [Multimodal generation](README.md)

## Request count is not a compute budget

Two image requests can have very different patch counts; two video generations can have different latent lengths, resolutions, guidance modes, and adapter settings. Treating them as two interchangeable sequence slots obscures real work and memory. Current engines already batch multimodal requests. The research opportunity is to reduce padding and head-of-line waiting while preserving each pipeline's actual compatibility constraints.

Qwen2.5-VL's dynamic spatial resolution demonstrates input heterogeneity. Current vLLM-Omni diffusion execution documents another kind: compatible independent requests may share a complete pipeline wave, while step-capable pipelines can admit work between denoising steps. Compatibility still depends on shapes, guidance, output counts, LoRA configuration, and pipeline-specific support. A nominal batch size alone does not describe either execution.

## One mixed queue

Suppose three requests arrive in order: a 512² image with one adapter, a 1024² image with another, and a second 512² image matching the first. A FIFO scheduler may execute the first separately because the next request is incompatible, even though a compatible request is waiting behind it. Searching further into the queue could form a better batch, but also delays the large request. The correct comparison includes waiting time and fairness, not only device throughput.

For padded encoder tensors, an illustrative utilization is U=sum_i V_i/(n max_i V_i), where V_i is the per-item token count. Counts 256 and 1,024 give U=0.625 for two padded rows. Packed execution can avoid that padding, but needs correct sequence boundaries, attention masks, positional metadata, and output reconstruction. Some attention costs scale with sum_i V_i² rather than (sum_i V_i)²; packing must not accidentally introduce cross-item attention.

Diffusion is different. Each step updates a request-specific latent and solver state. Step batching must maintain step index, random state, conditioning, guidance, and output association per request. A packed kernel is insufficient if the pipeline's scheduler or VAE assumes one common shape. The checked Omni documentation explicitly limits some pipelines and notes that a supported packed path does not necessarily improve throughput.

## Conditions and current limits

No new training is needed to improve batch formation while retaining the same inputs and model. Use released model weights, processor, VAE, and text encoder, and preserve the per-request sampler. Lowering image resolution or shortening video is a workload/quality change rather than a scheduling improvement. BF16/FP16 kernels may require shape alignment; quantized paths and graph capture can impose different restrictions. CUDA support in a source implementation is not automatic availability on another accelerator.

At the checked Omni state, diffusion cache backends are unsupported in step execution. Different LoRAs or scales separate compatible batches. Helios is limited to a single request; MiniMax H3's packed batching requires FlashAttention, and its documented batching does not improve measured throughput.

`max_num_seqs` bounds concurrent requests; continuous step batching additionally requires a pipeline implementing the step contract.

## Experiments that reveal the right owner

Construct a matrix varying resolution, image count, video duration, guidance, and adapter independently. Preserve original shapes and arrival timestamps. Compare FIFO with compatibility-aware batching at matched waiting limits, then compare padded and supported packed kernels under the same batch membership. This separates scheduling from operator layout.

Record tokens or latent elements per batch, padding ratio, queue ages by shape, actual batch size, graph replay versus eager time, recompilation, peak memory, TTFT or first-frame tails, complete-generation latency, failures, and SLO-compliant goodput. Include a rare large shape so a throughput-oriented scheduler cannot hide starvation. Check output ownership and fixed-seed reproducibility within the numerical tolerance of the selected backend.

If packing helps the kernel but not the service, examine queueing and incompatible downstream stages. If grouping improves throughput but large-shape tails explode, the batching policy traded fairness for utilization. The remaining design space is a shape-aware policy at the existing scheduler boundary, with supported kernel/pipeline contracts.

## Sources and checked state

Checked 2026-10-14.

- [Qwen2.5-VL, arXiv:2502.13923v1](https://arxiv.org/html/2502.13923v1): dynamic shapes and training sample packing as model background.
- [Omni diffusion execution modes](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/diffusion/execution_modes/) and [pinned source](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/user_guide/diffusion/execution_modes.md): current compatibility and pipeline restrictions; main `37f094a` dated 2026-10-13, released `v0.30.0` dated 2026-09-25.
- [EAServe, arXiv:2609.31551v1](https://arxiv.org/html/2609.31551v1): recent encoder batch timing research; the paper does not establish a specialized heterogeneous-shape packing implementation.
