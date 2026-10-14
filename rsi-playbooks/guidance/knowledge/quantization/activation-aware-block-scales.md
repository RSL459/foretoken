<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Activation-aware block-scale selection

English | [简体中文](activation-aware-block-scales_zh.md)

Two blocks with the same weight reconstruction error can have very different effects on a model. A scale selected from weight maxima alone ignores which input directions the workload actually uses. Recent NVFP4 calibration methods address this without introducing a new inference representation.

## Optimize the error that reaches the output

Use column-vector inputs and `Y = W X`, with `W[N,K]` and calibration inputs `X[K,T]` for T tokens. For a scale `s`, let `Q(W,s)` be the reconstructed quantized weights and `Δ = Q(W,s) − W`. Weight MSE is `||Δ||²_F/(NK)`. Calibration output squared error instead minimizes

```text
E = ||Δ X||²_F = tr(Δ H Δᵀ),   H = X Xᵀ.
```

`H` accumulates uncentered input second moments and is often called a local Hessian in this setting. Dividing E by NT gives output MSE; fixed normalization leaves the minimizing scale unchanged. The relevant curvature is for this local reconstruction objective. For uncorrelated, zero-mean channels with second moments 100 and 1, equal weight errors contribute output errors in a 100:1 ratio. Correlations also matter: errors can reinforce or cancel on frequently observed input directions.

Model Optimizer's Local-Hessian method partitions the input axis into 16-element NVFP4 blocks. It accumulates a `16×16` second-moment matrix for each block, evaluates candidate representable FP8 scales, and selects the scale minimizing `Δ_b H_b Δ_bᵀ`. Its announcement describes a sweep of 126 positive nonzero FP8 scale candidates. Block independence makes the search manageable but drops error interactions between different blocks.

Calibration proceeds by collecting activations, accumulating block statistics, choosing scales, and exporting ordinary NVFP4 weights and scale metadata. Layerwise calibration can feed later layers the outputs of earlier fake-quantized layers, rather than assuming all inputs remain BF16. The resulting checkpoint does not require a Local-Hessian inference kernel: only the usual kernel for its exported NVFP4 format.

## Floating-point codebooks change scale selection

Four Over Six supplies a related intuition. E2M1 has uneven spacing; its largest positive values include 4 and 6. The conventional scale puts the maximum near 6. An alternative places it near 4, redistributing reconstruction precision across the block. The method chooses between scale rules using reconstruction error. “Four” does not mean changing the payload bit width or replacing the native E2M1 codebook.

Ignoring scale-encoding error, for a block `[10,20,30,40]`, scaling its maximum to 4 gives scale 10 and exact E2M1 values `[1,2,3,4]`; scaling it to 6 gives scale 40/6, maps 30/scale = 4.5 to 4, and reconstructs that value as about 26.67. Another block can favor 6, so both candidates must be reconstructed and compared. The paper explicitly excludes applying the same 4/6 choice to MXFP4: the required 1.5× scale change is not generally representable with power-of-two E8M0 scales. The current Four Over Six repository offers an MSE-based default, Blackwell CUDA/Triton implementations, and a slow PyTorch reference. Its README also discusses newer adaptive block-scaled types; those are separate from the 4/6 principle. ModelOpt exposes Local-Hessian as an offline calibration method.

## Where the calibration still matters

These methods fit dense and MoE linear weights exported as NVFP4, with deployment eligibility determined by the existing runtime backend. The unresolved choice is the calibration distribution: domain, language, context length, and rare expert coverage. A sparse expert with almost no calibration tokens has weak statistics even if the optimizer searches scales exhaustively. A stronger block objective cannot recover information absent from calibration.

Use a discriminating comparison of maximum-based, weight-MSE, and Local-Hessian scales while keeping payload format and inference backend fixed. Record weight error, output reconstruction error on held-out activations, expert token counts, and downstream task quality. Include a distribution-shift slice, such as code or long-context inputs excluded from calibration. Then measure complete service latency with the same checkpoint layout; a quality gain with unchanged kernel cost is a valid result even without faster GEMM.

If quality remains poor, examine cross-block error and underrepresented layers before increasing calibration indefinitely. More expensive calibration is justified by improved held-out behavior, not by a lower training-set reconstruction loss alone.
## Sources

Checked 2026-10-14; ModelOpt snapshot `b5f10f8bf96201241c35b86498557bd6fdde10ca`.

- [Local-Hessian method, API, and limitations](https://nvidia.github.io/Model-Optimizer/announcements/local-hessian.html).
- [Calibration implementation](https://github.com/NVIDIA/Model-Optimizer/blob/b5f10f8bf96201241c35b86498557bd6fdde10ca/modelopt/torch/quantization/model_calib.py).
- [Four Over Six paper, arXiv 2512.02010v5](https://arxiv.org/abs/2512.02010) and [author implementation](https://github.com/mit-han-lab/fouroversix). Method and implementation sections were checked against the author's repository at `dadfad6901d473a734fe71e0b082e70ee993e23a` (2026-04-21).

[Quantization questions](README.md) · [Knowledge index](../README.md)
