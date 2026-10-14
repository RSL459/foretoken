<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce visual prefill through encoder and KV reuse

English | [简体中文](reduce-visual-prefill-through-encoder-and-kv-reuse_zh.md) | [Multimodal generation](README.md)

## Which repeated work can actually disappear?

Repeated questions about one image offer two different reuse opportunities. A vision encoder produces image embeddings independently of the question, so identical processing with identical encoder weights can reuse them exactly. Decoder KV states may depend on preceding text, positions, and other images. Reusing those states across a changed prompt is not generally exact prefix caching. VLCache, published in December 2025, investigates that second opportunity; it should not be confused with the encoder cache already present in current engines.

Visual token count is an important input to this decision. Qwen2.5-VL uses 14-pixel spatial patches and merges four neighboring features before the language model. A resized image of height H and width W therefore produces approximately HW/784 language-side visual tokens, excluding model-specific framing. A 448×448 image gives 256 tokens; doubling both dimensions gives 1,024, not 512. Video additionally groups temporal frames. The trained processor and model determine these counts.

## One execution

Suppose two requests ask different questions about the same document scan. First, decode and resize the scan with the checkpoint's processor. Look up the encoder embedding using the engine's existing identity mechanism. On a miss, execute the ViT and projector, publish the embedding, and place it among the decoder's text embeddings. Normal decoder prefill creates contextual KV states.

VLCache additionally stores vision KV before rotary position encoding. On a later exact-image hit, it retrieves the embedding and vision KV, applies the appropriate positional handling, and recomputes a selected prefix of vision tokens at each layer while reusing the remainder. The paper chooses layer-dependent recomputation fractions from a small calibration set, with fractions constrained not to increase with depth. This is selective recomputation, not similarity matching between two different pictures. The paper uses exact pixel identities and describes Tair KVCache Store.

The mathematical distinction is useful: E(image) can remain constant while KV_l(image, preceding_text, positions) changes. Exact E reuse removes vision computation; approximate KV reuse can also remove much of decoder visual prefill. Combining their hit counts hides which work was saved and which approximation affected answers.

## Conditions and quality

Use the checkpoint's released weights and processor together. The Qwen report links public Qwen2.5-VL checkpoints; VLCache evaluates Qwen2.5-VL and Qwen3-VL families without retraining them. Calibration selects reuse rates rather than producing a new language model. Its paper does not identify a public author repository, so a paper-described SGLang integration is not evidence of a generally available upstream feature.

BF16 or FP16 embeddings do not make contextual KV reuse exact. Quantizing cached embeddings introduces a separate approximation and must be evaluated separately. NVIDIA GPU results do not establish behavior on another accelerator, attention backend, or processor revision. Changing OCR resolution, image order, prompt position, or encoder/tower LoRA changes the reuse conditions. A textual question may require a tiny region whose contribution is lost in otherwise good aggregate scores.

## Experiments that distinguish the hypotheses

Compare four paths with the same checkpoint, processor, dtype, and generation settings: full recomputation; exact encoder reuse only; exact full-prefix KV reuse where the prefix genuinely matches; and VLCache-style cross-context selective reuse. Construct repeated images with changed questions, image order, and preceding instructions, alongside cold images. Include small-font OCR, counting, localization, and conflicting textual premises.

Record processor time, encoder GPU time, decoder prefill time, transferred bytes, cache memory, item-level hit rates, service P50/P95/P99 TTFT, output length, and successful requests per second meeting a latency target. Score each question family and inspect changed answers, rather than reporting only a mean. If encoder time vanishes but prefill remains unchanged, the exact cache is functioning; a larger gain requires another cause. If cross-context reuse fails while exact-prefix reuse succeeds, investigate contextual dependence rather than cache lookup speed.

The remaining research question is how to choose recomputation under changing prompts and workloads without invalidating quality.

## References

- [VLCache, arXiv:2512.12977v1](https://arxiv.org/html/2512.12977v1): December 2025 method and experiments; no author code link identified in the paper.
- [Qwen2.5-VL report, arXiv:2502.13923v1](https://arxiv.org/html/2502.13923v1): processor, spatial merging, training, and release links.
- [vLLM encoder-cache owner](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/encoder_cache_manager.py): source at commit `6849ca6` dated 2026-10-13; exact embedding reuse is implemented.
