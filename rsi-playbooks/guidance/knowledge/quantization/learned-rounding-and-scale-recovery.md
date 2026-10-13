<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Learned rounding and scale recovery

English | [简体中文](learned-rounding-and-scale-recovery_zh.md)

Round-to-nearest minimizes each scalar's immediate error, not the output error of a transformer block. When straightforward calibration loses quality, optimization can recover accuracy while retaining an existing low-bit deployment format. The useful distinction is what is learned: rounding decisions, scales, or the underlying model weights.

## Optimize a block rather than isolated values

Let `F_l` be a BF16 block and `F̂_l` its fake-quantized version. A reconstruction objective uses calibration hidden states `h`:

```text
L_block = Σ_h ||F̂_l(h; θ) − F_l(h)||².
```

For integer quantization, a rounding variable can choose between neighboring representable levels. For floating-point formats, neighboring levels are unevenly spaced, and scale/clipping choices affect which codebook interval contains a value. The objective therefore needs the actual fake quantizer, not a uniform-integer approximation passed off as FP4.

The checked llm-compressor AutoRound NVFP4 example describes learning `V`, `α`, and `β` for rounding and clipping while processing decoder layers sequentially. A practical flow captures block inputs and BF16 outputs, optimizes quantization parameters against those outputs, freezes the choices, exports compressed-tensors weights, and loads them through vLLM. This is already an upstream workflow. Its benefit is improved reconstruction with the same final format, not a new runtime optimizer. The published Llama-3.1 example also illustrates why more iterations are not automatically better: 200 iterations improve one GSM8K extraction score over zero iterations while reducing another. Evaluate the intended answer/scoring behavior, not just reconstruction loss.

Scale learning takes a different route. Model Optimizer's current NVFP4 documentation trains per-block weight scales, represented through `amax` parameters, with fake quantization and straight-through estimators. It supports scale-only and joint weight/scale training. MSE calibration initializes the scales; the examples monitor a distillation-style KL objective. The exported scales are still quantized to the NVFP4 format's FP8 representation, so an apparently good continuous scale must survive that projection.

For a 16-weight block, scale-only learning has one parameter rather than sixteen trainable weights. This reduces trainable and optimizer state, not the cost of every forward/backward computation. The official announcement suggests that short scale-learning runs can converge; its learning-rate and step examples are starting points from those models, not universal requirements. Current documentation limits the feature to per-block NVFP4 weight scales; global and activation-scale learning are described as extensions.

## Where the extra effort can pay off

These approaches are relevant when W4A4 NVFP4 or another supported low-bit format is close to an acceptable quality threshold. They do not compensate for an unsupported kernel, a broken export, or an architecture mismatch. Sequential block reconstruction may miss cross-layer interactions; scale-only learning cannot move a badly positioned weight freely; joint learning has higher resource and data costs.

The remaining design space is choosing the smallest recovery procedure that improves held-out behavior: calibration selection, expert coverage, block grouping, initialization, and whether scales alone are sufficient. MoE models need actual routed tokens in calibration. An expert with little activity should not be declared recovered solely because the overall block objective fell.

## Separate recovery from deployment performance

Compare direct calibration, existing AutoRound, and scale-only recovery on the same model and calibration/held-out split. Record calibration duration, peak memory, reconstruction error, task scores, and per-expert coverage. If comparing joint training, report its different trainable-state budget. Reload the exported checkpoint in the intended engine and check that the kernel and scale granularity match the planned format.

Local timing should include activation quantization and both projections of a representative MLP or MoE stage. At service level, observe quality, TTFT, TPOT, successful token throughput, and output lengths. The ideal recovery changes quality without adding runtime operators, but an export that silently selects a different backend needs separate attribution.
## Sources

Checked 2026-10-14; snapshots are listed in the [category index](README.md).

- [llm-compressor AutoRound NVFP4 example](https://github.com/vllm-project/llm-compressor/tree/990fdd2fb41af48f105dbdebd088a96b627701b1/examples/autoround/quantization_w4a4_fp4).
- [Model Optimizer scale-learning method and current scope](https://nvidia.github.io/Model-Optimizer/announcements/scale-learning.html).
- [vLLM deployment formats](https://docs.vllm.ai/en/latest/features/quantization/modelopt/).

[Quantization questions](README.md) · [MoE execution](../moe-execution/README.md) · [Knowledge index](../README.md)
