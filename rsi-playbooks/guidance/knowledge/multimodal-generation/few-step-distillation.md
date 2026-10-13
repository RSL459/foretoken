<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Few-step generation changes the trained model

English | [简体中文](few-step-distillation_zh.md) | [Multimodal generation](README.md)

## Separate model compression from execution acceleration

Reducing a diffusion sampler from many evaluations to a few is not equivalent to making the original kernels faster. Distillation trains another predictor to reproduce a trajectory or output distribution with fewer steps. Changing weights, solver, guidance, and training objective can change diversity and prompt fidelity even when examples look similar. A service comparison should expose those changes rather than describe a distilled model as a lossless optimization.

LCM and LCM-LoRA provide the historical consistency-model foundation. More recent streaming video work must also address the gap between training on clean or teacher-generated history and consuming the model's own imperfect history during inference. The public NVIDIA rCM repository, including Causal-rCM, provides a concrete 2026 implementation to study this issue. Existing few-step models are the starting point; the remaining question is how their training and serving assumptions survive a target workload.

## One training and inference path

A teacher predicts a high-quality denoising trajectory. A consistency objective trains a student to map different noisy states on that trajectory toward a common denoised result, allowing large jumps at inference. Classifier-free guidance can be incorporated during distillation, so the resulting student does not necessarily use the original teacher's guidance scale or sampling recipe. LCM-LoRA expresses the distilled update as low-rank weights compatible with its specified base model; it is not a universal adapter for every diffusion checkpoint.

For causal video, generate a first chunk with a few denoising evaluations, store the allowed history, then generate the next chunk conditioned on that history. If training always supplies clean historical chunks but inference supplies imperfect generated ones, the conditioning distribution changes. Causal-rCM combines teacher-forcing consistency training with self-forcing, on-policy distribution-matching distillation. Self-forcing rolls out the student and trains against states it will encounter, while teacher-forcing supplies a complementary supervised trajectory signal. The README recommends staged dCM warmup, sCM, then DMD with sCM for robustness; that recipe is not simply a different inference flag.

The causal guide first adapts a bidirectional Wan checkpoint into a causal teacher, then distills the student and refines it with self-forcing DMD. Ordinary chunk inference adds a clean zero-time context pass after each chunk. Reusing the last noisy state can remove that pass only with matching noisy-context training and chunk settings. Count these context passes as well as denoising steps.

A useful conceptual budget is T = N_student T_DiT + T_text + T_VAE + T_delivery. Lowering N_student only attacks one term. Four-step generation may expose VAE decoding or transfer as the new bottleneck, so combining a model replacement with a kernel change requires separate attribution.

## Weights, hardware, and quality

The rCM repository describes Wan2.1 T2V 1.3B and 14B teachers, VAE and umT5 assets, plus optional distilled rCM/Causal-rCM checkpoints from its linked asset repository. Training code and configuration are public. The inspected instructions do not establish that every advertised configuration has a downloadable trained checkpoint; check the actual files before selecting a candidate. Reproducing teacher weights alone does not reproduce distillation.

Its environment specifies CUDA, PyTorch, FlashAttention, FSDP2, and optional Ulysses context parallelism. These are implementation dependencies, not accelerator-neutral availability. State the actual BF16/FP16 training and inference configuration; lower-precision inference adds a different quality variable. Image LCM's documented FP16 warning also demonstrates why dtype should not be treated as incidental.

Distribution matching can improve realism without preserving every prompt or diversity mode. Long autoregressive rollouts can drift, repeat, or change subjects even when short clips score well. The correct constraint may be an acceptable quality operating point, not exact equality to the teacher.

## A comparison that identifies the cause

First compare the teacher with its intended sampler to a released or reproduced student with its intended few-step sampler. Then optimize the student's execution while keeping its weights and sampler fixed. If caching is added, evaluate it as a third change. Preserve prompts, seeds where meaningful, resolution, video duration, negative prompts, and guidance semantics in the run record.

Measure time to first usable frame, complete-clip latency, steady video frames per second, GPU memory, successful quality-qualified outputs per second, and cost per accepted video-second. Evaluate prompt adherence, identity consistency, motion, diversity across seeds, and drift over increasing duration. Compare teacher-forced and self-forced students at matched inference budgets if the hypothesis concerns rollout robustness; a short-clip latency result cannot answer that question.

The practical research space is reliable few-step operating points and long-horizon behavior, not relabeling existing LCM support as a new serving feature.

## Sources and checked state

Checked 2026-10-14.

- [NVIDIA rCM](https://github.com/NVlabs/rcm/tree/ed3cb14dd936f92cdc9f9381af7369991509b41f): README, asset instructions, and causal training entry points; commit `ed3cb14` dated 2026-06-25.
- [Causal-rCM guide](https://github.com/NVlabs/rcm/blob/ed3cb14dd936f92cdc9f9381af7369991509b41f/Causal_rCM.md): causal training/inference entry point; availability is model/configuration-specific.
- [LCM author repository](https://github.com/luosiallen/latent-consistency-model): training and released LCM/LCM-LoRA families as foundational evidence, not a recent optimization candidate.
