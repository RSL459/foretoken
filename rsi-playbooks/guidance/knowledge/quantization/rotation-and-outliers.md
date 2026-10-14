<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Rotation, outliers, and runtime cost

English | [简体中文](rotation-and-outliers_zh.md)

An activation block containing one very large coordinate can spend most of its quantization range on that coordinate. Rotation spreads energy across coordinates before quantization. Its value depends on both the resulting error and whether the transform can be folded into weights or must execute online.

## Change coordinates, preserve the linear map

For row-vector inputs, `Y = X Wᵀ`. If `R Rᵀ = I`, set `X′ = X R` and `W′ = W R`; then `X′ W′ᵀ = X Wᵀ`. Quantization is applied after this exact change of coordinates, so it sees a different distribution even though the unquantized computation is unchanged.

A two-coordinate example makes the effect visible. Rotating `[a,0]` with a normalized Hadamard matrix produces `[a/√2,a/√2]`: the maximum magnitude falls while the norm is preserved. In a long vector, a transform may reduce domination by isolated channels. It does not guarantee that every block becomes well behaved. A global rotation, a block rotation, and a permutation produce different distributions relative to the 16- or 32-value scale groups.

Execution starts by collecting channel and block statistics, selecting a transform, folding its offline parts into adjacent weights, inserting unavoidable online transforms, and only then calibrating quantizers. Reusing scales from before the rotation confounds the comparison. Pointwise nonlinearities generally do not commute with arbitrary rotations; a rotation cannot simply be pushed through SiLU or a gate product. The output of such an operation may require an online transform paired with a transformed down-projection weight.

SpinQuant's checked implementation rotates embeddings, attention inputs/outputs, MLP inputs/outputs, and the language-model head. Its down-projection handling includes an inverse Hadamard weight transform. These are concrete model rewrites, not permission to rotate arbitrary modules in a hybrid architecture. Biases, normalization, residual branches, shared experts, and tied weights must preserve the same coordinate system.

## Existing support and newer research

llm-compressor already lists SpinQuant and QuIP among supported methods. SpinQuant's author repository includes learned rotations and an ExecuTorch export path. Deployment in vLLM depends on the exported format and support for the required runtime transforms.

TORQ, arXiv 2605.19561v1, separates MXFP4 activation error into inter-block energy imbalance and intra-block codebook underuse. Its method constructs `R = R_inter ⊗ R_intra`: Givens rotations equalize covariance diagonals across blocks, while within-block rotations alternate with scale updates to reduce `Σ_j (p_j−1/J)²`, the imbalance in codeword occupancy. The method section and execution diagram retain online activation rotations and fold their inverse into the consumer's weights. The paper reports quality and RTX 5090 speed results; upstream serving integration remains unverified. The useful next question is whether this two-level structure improves held-out quality enough to pay for its online transforms.

For NVFP4, MXFP4, and integer W4A8/W4A16 paths, the practical remaining question is which transformation scope improves quality with acceptable execution overhead. An online transform can cost more than the quantized GEMM saves at tiny decode batches. A denser transform can also increase weight error after repacking or disrupt an otherwise fused activation-quantization path.

## Measure error and the transform together

Compare no rotation, an existing fixed Hadamard method, and an existing learned rotation using the same calibration corpus and final format. Inspect block maxima, variance spread, clipping, codebook occupancy, and held-out layer output error. Verify the BF16 transformed model before attributing errors to quantization. Time online transforms, quantization, and GEMM as one stage at real decode and prefill shapes.

At service level, measure answer quality, TTFT, TPOT, and actual generated lengths; include calibration-domain and shifted-domain prompts. A quality recovery that costs latency may still enable a smaller deployment, but that trade-off must be stated.
## Sources

Checked 2026-10-14.

- [SpinQuant source, commit 8f47aa3f00e8662caf1a484153920a07e5281c3a](https://github.com/facebookresearch/SpinQuant/blob/8f47aa3f00e8662caf1a484153920a07e5281c3a/eval_utils/rotation_utils.py), dated 2025-02-14.
- [Current llm-compressor methods](https://github.com/vllm-project/llm-compressor/tree/990fdd2fb41af48f105dbdebd088a96b627701b1).
- [TORQ method, execution diagram, and limitations, v1](https://arxiv.org/abs/2605.19561).

[Quantization questions](README.md) · [Kernel design](../kernel-design/README.md) · [Knowledge index](../README.md)
