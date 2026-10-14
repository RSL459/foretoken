<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce stream-rendering work through incremental text decoding

English | [简体中文](reduce-stream-rendering-work-through-incremental-text-decoding_zh.md) · [Host and streaming](README.md) · [Knowledge](../README.md)

## A token is not a printable chunk

An engine can produce token IDs regularly while a user sees irregular text. Byte-level tokenizers may split a Unicode character across tokens. Decoder rules can depend on preceding tokens, and special-token spacing or stop strings can withhold text that is already computed. Downstream reasoning or tool parsers introduce another boundary. These are different from device stalls and must be understood before interpreting inter-chunk latency as decode speed.

Consider a character whose UTF-8 bytes span several token IDs. Decoding each token independently can emit replacement characters; concatenating those decoded strings does not recover the correct character. An incremental decoder retains enough token or byte context to emit a stable suffix. Its output cadence depends on the content, not just token count.

## Work grows with the retained representation

Repeatedly decoding the entire generated prefix of lengths 1 through n performs work proportional to 1 + 2 + ... + n, or O(n²), if decode cost is linear in prefix size. Repeatedly constructing the entire accumulated string can have the same effect even with a fast native decoder. An incremental implementation aims for work proportional to newly consumed tokens plus the context needed to resolve boundaries. This is not a universal complexity guarantee: tokenizer rules, parser replay, stop matching, and response representation still matter.

The cited vLLM detokenizer has native `DecodeStream` and helper-based incremental paths. It maintains output positions and distinguishes accumulated output from delta output. SGLang's detokenizer manager tracks surrogate/read offsets, unsent text, and deferred chunks; grouped `batch_decode` calls serve compatible decoding settings. The research question is whether the active path still revisits long history, repeats conversions, or spends more time in serialization than decoding.

Stop-string semantics impose necessary buffering. For a longest stop string of L characters, vLLM withholds up to L − 1 characters while generation continues when stop strings must be excluded. Otherwise an emitted suffix could later become part of a forbidden stop marker. If tokens contribute few characters, this can delay visible text for multiple device steps. On completion the remaining permissible text must be flushed, and matched stop text trimmed according to the configured inclusion rule.

## Batching changes cadence and amortization

Let each output operation cost a fixed a plus b per token. Emitting k tokens together reduces average processing cost from a + b to a/k + b. For a regular token interval d, periodic groups of k add an average waiting time of approximately (k − 1)d/2 before emission. The estimate assumes uniform production and flushes on group completion; stop handling, bursts, and timeout flushing change it.

Batching may therefore help many short, fast streams while harming a single interactive stream. A bound based only on token count can trap the final partial group or delay cancellation. State also grows with active requests: tokenizer history, retained strings, parser state, and queued output are separate contributors. More decoder workers do not help a bottleneck in a shared output queue, nor do they balance work if routing concentrates long streams on one worker.

Fastokens is an existing optional vLLM backend for supported BPE tokenizer paths, documented for vLLM 0.23.0 onward with fastokens 0.2.0 or later. It does not cover every tokenizer mode. Compare backend cost using the actual tokenizer, output lengths, and concurrent streams.

## Separate text correctness from transport performance

Use a content matrix with ASCII, multilingual byte boundaries, long outputs, special tokens, tool delimiters, and stop strings crossing emission boundaries. Feed identical generated token IDs into the compared paths. Verify reconstructed final text and terminal flush first; a shorter output caused by premature stopping can look faster without performing the same work.

Then vary output length and active stream count independently. Record token-ready, decoded-text-ready, enqueued, and client-parsed-event times. Superlinear host cost versus output length suggests prefix replay or copying; cost proportional to active streams suggests per-event overhead or queue contention. Compare chunk-size distributions, bytes, native token usage, and per-request maximum gaps. A faster engine with larger chunks can increase observed ITL even while token throughput rises. Foretoken's current timing counts non-empty `choices`, including role and finish chunks, not individual tokens; inspect payloads before assigning a chunk gap to text generation.

## References

- [vLLM incremental detokenizer](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/engine/detokenizer.py): native/helper paths, stop buffer, and delta output; revision dated 2026-10-13.
- [SGLang detokenizer manager](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/detokenizer_manager.py): incremental offsets, deferred text, batched decoding, and final cleanup; revision dated 2026-10-13.
- [vLLM optimization documentation](https://docs.vllm.ai/en/latest/configuration/optimization/): fastokens version and tokenizer restrictions.
- [Foretoken chunk timing](../../../../benchmarks/src/benchmarks/integrations/streaming.py) and [metric definitions](../../../../benchmarks/docs/metrics.md): Foretoken `e6ae3df6`; ITL is a received-chunk interval.
