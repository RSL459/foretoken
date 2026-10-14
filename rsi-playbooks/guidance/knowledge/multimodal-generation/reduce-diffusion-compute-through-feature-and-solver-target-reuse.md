<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce diffusion compute through feature and solver-target reuse

English | [简体中文](reduce-diffusion-compute-through-feature-and-solver-target-reuse_zh.md) | [Multimodal generation](README.md)

## Why the cached quantity matters

A diffusion transformer repeatedly evaluates closely related latents. Skipping some evaluations can accelerate generation without training another model, but it changes the numerical trajectory. TeaCache and TaylorSeer establish two useful foundations: decide when a residual is reusable, or forecast a feature rather than holding it constant. The October 2026 AutoTarget paper asks a newer question: in a few-step model, which solver-facing quantity should be cached? These are approximation methods, not lossless kernel fusion.

vLLM-Omni integrates cache-dit for request-level diffusion execution; at the cited revision, diffusion cache backends are unsupported in step execution.

## One denoising interval

At an anchor step, TeaCache runs the expensive transformer and stores its residual. At later steps it computes a relative L1 change in timestep-modulated input, maps that indicator through a fitted polynomial, and accumulates the estimated changes. Below a threshold it adds the cached residual to the current input; above the threshold it runs the transformer and refreshes the cache. Model-specific calibration matters because the inexpensive indicator is only a proxy for hidden computation.

TaylorSeer instead stores features and finite differences from full evaluations. Between anchors it predicts a feature with a truncated Taylor expansion, for example F_hat(t+delta)=F(t)+delta F'(t)+delta² F''(t)/2. The derivatives are estimates from sampled features, not automatic differentiation of the whole sampler. Higher order can improve forecasting but adds state and becomes unreliable across abrupt feature changes.

AutoTarget works at the solver boundary. For linear flow, x_t=(1-t)c+t e and v=e-c, so an anchor supplies c=x_a-t_a v_a and e=x_a+(1-t_a)v_a. Under deterministic Euler and the paper's stated conversion assumptions, reusing velocity, clean endpoint, or noise endpoint yields the same cached trajectory between anchors. Reusing a displacement h_a v_a is different when the next interval is h_j: the displacement error is proportional to (h_j-h_a)v_a. A cache name alone therefore does not specify its semantics.

Its calibration records exact solver states, evaluates admissible targets at matched anchor/reuse states, and compares decoded RGB error. Selection abstains when the best candidates are too close. The current Omni cache guide advises against TaylorSeer for few-step distilled models; AutoTarget's solver-facing target selection is a different mechanism, not evidence that TaylorSeer became appropriate for those pipelines.

## Conditions, weights, and quality

TeaCache and TaylorSeer use existing image/video diffusion checkpoints without retraining. AutoTarget's public code supplies codecs and selection logic for FLUX, PixArt-LCM, and HunyuanVideo paths; it is not a release of new weights. Obtain the original checkpoint, VAE, text encoder, and scheduler together. Reusing a calibrated threshold across a new resolution, guidance setting, dtype, or solver is a separate hypothesis.

FP16/BF16 cached features may accumulate prediction error. FP8 quantization would add another approximation; avoid attributing its effects to the cache schedule. NVIDIA-focused reference implementations do not establish kernel support on other devices. PSNR against a reference image diagnoses trajectory deviation, but prompt adherence, text rendering, motion, and diversity need independent assessment. A smooth feature sequence can still carry semantically important changes.

## A useful comparison

Hold checkpoint, prompt, seed, resolution, guidance, dtype, and solver fixed. Compare no cache, residual reuse, feature forecasting, and solver-target reuse with the same number of full transformer calls. Repeat with uniform and nonuniform step schedules; this distinguishes better target semantics from simply evaluating more often. Few-step workloads deserve their own comparison because one skipped call is a large fraction of the trajectory.

Record transformer-call count and time, predictor/reduction time, VAE time, peak cache memory, total service latency, queueing, images or video-seconds meeting quality and latency targets, and failed requests. Inspect outputs across prompt categories and motion changes, not just the best example. If an advantage disappears at matched call count, it came from refresh frequency rather than the claimed target. If it appears only with nonuniform intervals, test the displacement conversion directly.

## References

- [TeaCache, arXiv:2411.19108v1](https://arxiv.org/html/2411.19108v1) and [author code](https://github.com/ali-vilab/TeaCache): residual and cumulative-proxy mechanism as background.
- [TaylorSeer, arXiv:2503.06923v1](https://arxiv.org/html/2503.06923v1) and [author code](https://github.com/Shenyi-Z/TaylorSeer): forecasting recurrence and model entry points.
- [AutoTarget, arXiv:2610.03577v1](https://arxiv.org/html/2610.03577v1): submitted 2026-10-02; method. [Public implementation](https://github.com/wali1024-offical/AutoTarget/tree/e91a428b8bbc37a6661576a182e39e94e3cc55dd) at `e91a428`, dated 2026-10-01.
- [Omni execution modes](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/diffusion/execution_modes/) and [cache-dit documentation](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/user_guide/diffusion/cache_acceleration/cache_dit.md): source at `37f094a`, dated 2026-10-13; release `v0.30.0` was published 2026-09-25.
