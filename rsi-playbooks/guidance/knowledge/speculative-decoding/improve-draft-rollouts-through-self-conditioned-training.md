<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Improve draft rollouts through self-conditioned training

English | [简体中文](improve-draft-rollouts-through-self-conditioned-training_zh.md) | [Speculative decoding](README.md)

## Why the draft source matters

A small language model, an EAGLE-3 module, and native multi-token prediction (MTP) heads are not interchangeable sources of proposals. They differ in training inputs, dependence on the target checkpoint, recurrent draft history, and loading requirements. Each method requires compatible trained weights. The current research opportunity is reducing train/serve mismatch and useful training cost.

A standalone drafter is a second token-level language model with its own prefix processing. EAGLE-3 also adds a separately trained draft module, but conditions on internal target features and can reuse target embeddings/output projection through the engine's model-specific path. Native MTP is part of a supported target architecture's trained prediction machinery; it often needs no independently supplied model. Some supported assistant paths still take a separate checkpoint. Thus “one model” means one target with native auxiliary machinery, not free prediction or universal checkpoint compatibility.

## Training and one inference iteration

EAGLE-3 fuses low-, middle-, and high-level target representations instead of regressing to the target's final feature as older EAGLE did. The draft combines fused features with token embeddings and predicts tokens. Later speculative positions have no verified target features yet, so the draft feeds back its own hidden outputs. Its training-time test simulates this feedback, exposing the module to the inputs it will create during a multi-step draft. Teacher-forcing accuracy alone does not measure that behavior.

One iteration begins with a committed prefix and target-derived features. The draft extends a chain, or expands a tree using the same module. The target evaluates the proposed causal paths in a parallel verification pass. Exact verification commits only an accepted path and correction/bonus output. The rejected suffix is discarded; subsequent draft history is rebuilt from verified features and committed tokens. Native MTP follows the same outer draft/verify/commit discipline, but obtains proposals from model-specific prediction layers. Reusing one trained head several times is not equivalent to owning several independently trained future-position heads.

Training data must preserve target identity, tokenizer, chat template, selected feature layers, position conventions, and loss masks. On-policy target responses expose the target's actual continuation behavior; offline recorded features reduce repeated target forwards but fix that feature/data distribution. Online capture changes where features are produced, not whether the draft is trained. A target update or quantization/backend change can alter feature and probability alignment even when dimensions still match.

## Cost and current implementation

For a K-position chain, let a[j] be the probability of accepting position j conditional on all preceding drafts being accepted. Expected accepted draft length is sum_j=1..K product_i=1..j a[i]. For example, [0.9, 0.9, 0.5, 0.5] gives 2.3175 accepted drafts, while [0.8, 0.8, 0.8, 0.8] gives 2.3616. Better first-position accuracy alone does not identify the better rollout. Nor does the latter win if it requires a significantly slower draft layer or feature path.

The useful lifecycle cost includes training/capture, auxiliary weight residency, feature movement, draft forwards, target verification, and correction. For repeated service use, compare training investment with accumulated latency/capacity benefit, rather than reporting inference savings without the weights-production requirement. Native MTP can save separate feature extraction or loading, but still performs auxiliary computation and inherits its model's training choices.

SpecForge commit `fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa` already provides a unified `specforge train --config ...` entry and online/offline EAGLE3 recipes. Its documented offline paths consume recorded features; online target inference is owned by a SGLang capture service, not silently run inside the trainer. vLLM and SGLang expose EAGLE3 and supported native MTP inference paths.

## Experiments and remaining questions

Use a matching public draft/target pair first; for a new target without weights, classify the candidate as a training project. Compare teacher-forced and self-conditioned rollout on identical held-out prefixes, recording reached counts, first failure position, accepted chain length, and feature-capture volume. Separate languages, code, dialogue, and reasoning to reveal alignment failures hidden by aggregate accuracy.

For a training change, hold target, data, training budget, architecture, and serving configuration constant. Compare checkpoints at explicit optimizer steps. Distinguish marginal top-1 agreement from prefix survival and true stochastic serving acceptance after temperature/top-p processing. Inspect BOS duplication and template formatting before attributing low acceptance to insufficient training. Keep the formatted prefixes identical across comparisons; vLLM's benchmark preamble fix adds control over dataset chat templating.

Then measure unprofiled service TTFT, inter-token latency, completion time, throughput, memory headroom, and quality with no-spec and the existing draft. Profile feature capture, auxiliary LM head, and communication separately. Useful open questions are which rollout depths and task distributions deserve training weight, whether recorded features remain representative after an engine change, and whether higher acceptance offsets a larger auxiliary module.

## References

- [EAGLE-3 paper](https://arxiv.org/html/2503.01840): multi-layer fusion, removal of feature regression, and training-time feedback.
- [Pinned SpecForge training guide](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/docs/sections/basic_usage/training.md) and its [README](https://github.com/sgl-project/SpecForge/blob/fdcc2eddf1b56b5b24a5a15d3abcb366adfeb5aa/README.md): EAGLE3 capture/training recipes and metrics.
- [Pinned vLLM EAGLE](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/eagle.md) and [MTP guide](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/mtp.md), plus [SGLang source documentation](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx).
- [vLLM PR #25916](https://github.com/vllm-project/vllm/pull/25916) is merged, 2025-10-02, commit `1cab2f9cad22807150c93b4b5635ff884884ca5a`; its preamble correction adds `--skip-chat-template` to supported benchmark datasets.
