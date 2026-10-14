<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Balance mixed-precision quality, memory, and kernel cost

English | [简体中文](balance-mixed-precision-quality-memory-and-kernel-cost_zh.md)

A uniform low-bit model spends the same precision budget on layers with unequal sensitivity. Mixed precision can retain quality within a memory budget, but average bits alone do not predict latency. A useful assignment must respect the operators that the engine actually fuses and the kernels that the device can execute.

## Sensitivity chooses where precision matters

For each eligible operator `i` and candidate format `f`, Model Optimizer AutoQuantize estimates output-error sensitivity using a diagonal-Fisher approximation:

```text
S_i,f ∝ Σ_k g_i,k² (Y_i,k − Y^Q_i,f,k)².
```

Here `Y_i` and `Y^Q_i,f` are the reference and fake-quantized operator outputs; `g_i,k = ∂L/∂Y_i,k` is the scoring-loss gradient, and k indexes output elements. Scores aggregate calibration observations. It captures inputs, obtains output gradients, and replays candidate quantizers locally. An integer-programming search selects one format per operator or deployment group, minimizing summed sensitivity under an effective-bit budget. In schematic form:

```text
min Σ_i S_i,f(i),  subject to Σ_i N_i b_i,f(i) ≤ N_total b_target.
```

`N_i` is operator i's eligible weight count, `b_i,f` its modeled bits per weight in format f, `N_total = Σ_i N_i`, and `b_target` the requested average-bit budget. Only eligible quantizable weights count toward this budget; excluded embeddings or normalization parameters still occupy memory. Effective bits may include format metadata, but the objective is not measured service latency.

The current implementation groups deployment decisions such as QKV projections, gate/up projections, and sparse experts. Grouping matters because the runtime may merge those weights or require one shared quantization contract. Independently assigning three QKV formats can produce an assignment that is numerically attractive but cannot use the existing fused projection. Group sensitivity and cost aggregate member contributions; this does not model every interaction between their errors.

Consider two equal-size layer groups. If one loses much more quality at four bits, a four/eight-bit split may outperform a uniform six-bit budget in quality. Yet the four-bit group may execute through W4A16 while the eight-bit group uses a faster native FP8 kernel at large M. The bit-budget winner is not necessarily the latency winner.

## Use the existing search, measure the missing cost

AutoQuantize is already documented in the cited Model Optimizer development snapshot, including gradient and KL scoring. Its limitations include independently estimated layer sensitivity, diagonal curvature, grouped choices, and a proxy cost based on effective bits.

The useful remaining work is a workload-aware choice among deployable assignments. Measure each candidate group's complete stage cost at relevant decode and prefill shapes, including quantization, padding, epilogues, and format transitions. Reject unsupported format combinations at the existing exporter/runtime boundary rather than inventing a parallel checkpoint schema. Treat FP8, NVFP4, MXFP4, and BF16 as hardware-specific choices; native low-bit support, MoE layouts, and model-specific exclusions determine the available menu.

Changing a layer's precision can change scratch memory, graph capture size, and the largest feasible batch. Group costs therefore are not simply additive in a full service. A latency-aware extension should start with measured combinations and actual bottlenecks, not claim that replacing effective bits with one microbenchmark automatically solves the global assignment problem.

## An experiment that distinguishes budget from speed

Compare a uniform low-bit checkpoint, an existing AutoQuantize assignment at a similar memory budget, and one measured adjustment to a sensitive or slow group. Hold calibration data and quality evaluation fixed. Record resident weight memory, scale/padding overhead, conversion time, selected kernels, and held-out output quality. Use group-level reconstruction to diagnose sensitivity, not as the sole quality criterion.

Then run services at low concurrency and at the intended load. Observe TTFT, TPOT, successful token throughput, output lengths, and maximum admitted concurrency. A memory-saving assignment can win throughput through batching while losing low-load latency. If the adjusted group improves both quality and speed, preserve its model, shape, dtype, and device conditions rather than generalizing to all layers.
## References

- [AutoQuantize scoring, search, grouping, and limitations](https://nvidia.github.io/Model-Optimizer/announcements/autoquantize.html), ModelOpt snapshot `b5f10f8bf96201241c35b86498557bd6fdde10ca`.
- [vLLM executable ModelOpt formats](https://docs.vllm.ai/en/latest/features/quantization/modelopt/).
- [Current SGLang quantization backends](https://docs.sglang.io/advanced_features/quantization.html).

[Quantization questions](README.md) · [Heterogeneous execution](../heterogeneous-hardware/README.md) · [Knowledge index](../README.md)
