<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 块缩放格式与 kernel 布局

[English](block-scaled-formats.md) | 简体中文

四位检查点可以减少权重读取，却仍以十六位执行乘法。分析量化收益时，应先确认 kernel 实际接收的操作数、scale 的读取方式，以及转换发生在加载时还是每次前向中，而不只看“FP4”标签。

## 数值表示如何影响执行

线性层写作 `Y = X Wᵀ`，其中 `X[M,K]`、`W[N,K]`。块量化保存低位值 `q` 与 scale，按 `w ≈ s_block q` 重建。FP8 可以采用整张量、按通道或按块 scale。ModelOpt 还区分按通道权重、动态按 token 激活和块 FP8 weight-only；即使权重同为八位，它们的元数据读取与激活转换开销也不同。

MXFP4 每 32 个 E2M1 值共享一个 E8M0 二次幂 scale。NVFP4 每 16 个值共享 FP8 scale，并配合更大范围的外层 scale。两者只是数值本体均为四位，scale 编码和打包契约并不相同。暂不计补齐和外层 scale，平均存储分别约为 `4 + 8/32 = 4.25` 和 `4 + 8/16 = 4.5` bit。直接用“四位”估算内存会低估元数据成本。

执行链包含检查点解码、可选的一次性重排、激活量化、分块 GEMM、scale 应用和输出处理。原生 W4A4 kernel 消费低位权重与激活；W4A16 读取压缩权重，但激活保持高精度。如果先将整个矩阵反量化再做乘法，权重流量优势会被削弱。在 tile 内反量化可保留压缩读取，不过转换指令仍有成本。

以 `M=1, K=N=4096` 为例，每份权重只服务一个 token，读取成本突出。到 `M=256`，权重 tile 被更多 token 复用，计算吞吐和激活转换更重要。同一 W4A16 路径在前者获益、在后者变慢，并不矛盾。

## 当前实现与可继续研究的选择

已核对的 vLLM ModelOpt 文档包含 NVFP4 自动 backend 选择，以及原生 FP4 GEMM 不可用时的 Marlin W4A16 路径。当前 MXFP4 源码已实现按 backend 转换权重与 scale、维度补齐和 modular MoE dispatch。GPT-OSS 的 MXFP4 配置将普通线性层保留为非量化实现，专家权重是 MXFP4 不等于全模型 W4A4。

SGLang 也已有 FP8/FP4 自动选 kernel 与显式覆盖。加载器、块量化器和 dispatch 本身不是待开发候选。真正值得测的是目标模型在小 M 与大 M 下的交叉点、专家 token 分布、转换位置和补齐浪费。Blackwell 原生 NVFP4、AMD CDNA4 FP4、旧设备 weight-only 或转换格式路径要分别分析；相同 dtype 名称不能证明指令支持相同。

## 如何区分收益来源

从实际模型提取投影和专家形状，同时保留 stride、group size、scale 与 padding。比较已有原生低位 kernel、可用的 weight-only kernel 和 BF16，覆盖 `M=1`、几个真实 decode batch 与 prefill chunk。计时包含激活量化和输出处理，一次性重排单独报告；同时观察流量、实际 backend 和相同 BF16 输入下的输出误差。

再用相同输入输出长度、并发和模型语义比较完整服务，观察 TTFT、TPOT、成功输出 token、质量和剩余设备内存。更小的模型可能提高可接纳并发与吞吐，却不改善单请求 decode。局部收益消失时应检查调度、attention 与通信，不应仅据此否定低位计算。
## 来源

核对日期：2026-10-14；源码身份见[分类入口](README_zh.md)。

- [vLLM ModelOpt 格式与 backend 选择](https://docs.vllm.ai/en/latest/features/quantization/modelopt/)。
- [已核对 commit 的 MXFP4 实现](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/layers/quantization/mxfp4.py)。
- [SGLang 量化与 dispatch](https://docs.sglang.io/advanced_features/quantization.html)。

[量化问题索引](README_zh.md) · [知识索引](../README_zh.md)
