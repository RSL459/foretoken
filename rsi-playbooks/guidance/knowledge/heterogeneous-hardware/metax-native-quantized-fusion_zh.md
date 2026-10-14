<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# MetaX 量化阶段边界

[English](metax-native-quantized-fusion.md) | 简体中文

MetaX MACA 在 CUDA 风格的模型执行接口下，使用自身的量化、原生 GEMM、激活和通信 kernel 及 workspace。融合取决于这些阶段之间的真实边界。

## Dense INT8 已有明确执行链

已核对插件为 OOT 平台的 INT8 linear 注册 `MctlassScaledMMLinearKernel`。前向取得量化权重和 scale，将输入转为 contiguous，调用 `scaled_int8_quant`，再进入 MetaX scaled matrix multiplication wrapper。动态输入 scale 从本次输入计算，静态 scale 由层提供；需要非对称激活修正时走 zero-point-aware 变体。

对称量化可简写为：

```text
Y[m,n] ≈ s_x[m] s_w[n] Σ_k q_x[m,k] q_w[n,k] + bias[n]。
```

动态按 token scale 需要先沿 K 归约，然后 GEMM 才能消费 `q_x`。两阶段实现可能先读 BF16、写 INT8 与 scale，再重新读取。融合 producer 可避免部分中间张量，但输出布局和 scale 粒度必须匹配原生 consumer。只少一次 launch、却没有减少流量或损害并行度，不一定加速。

例如 RMSNorm 与量化融合，可以复用归一化已经读取的数据，前提是 consumer 接受所得 contiguous 或 packed INT8 布局。归一化维度若被 TP 分片，RMSNorm 就需要跨 shard 汇总平方和；局部融合 producer 必须保留这项归约，再进行归一化和量化。

## MoE 不能简单套用 dense 路径

MetaX 插件 commit `cec91763dbe968fe4478fc066f57ecf5877c3965` 的 compressed-tensors INT8 MoE 要求权重按通道、输入动态按 token 量化。它建立量化专家配置和 modular kernel，再传入 routing tables 与共享专家输入。当前 INT8 oracle 按支持检查，优先选择 Triton、batched Triton 和 batched DeepGEMM。具体选中的专家 kernel 决定 GEMM 执行方式和激活布局。

分析 gate/up GEMM、SiLU-and-multiply、再量化、down GEMM、路由权重应用与 combine 时，这个区别非常重要。适合 `[M,K]` 的 dense 融合不一定匹配 batched expert 格式。路由顺序、padding 与各专家 token 数会改变 scale 放置和中间张量大小。应读实际选择路径，而不是套用旧发行版或同名 kernel 的结论。

## 仍可能有收益的部分

原生 INT8 dispatch 与 modular MoE 集成已存在。可研究的是多余 contiguous copy、相容的 producer/quantizer 融合、中间结果重复读取、padding 和 workspace 生命周期。FP8、MXFP8 应另行追踪；INT8 wrapper 不证明某款 MetaX 设备有 NVFP4/MXFP4 原生算术。

实验使用匹配的 vLLM、插件、SDK 和算子库发行组合。插件 README 将 master 定位为跟随 upstream 的开发分支，发行版说明提供受支持的组件组合。

## 聚焦实验

截取一个真实 dense 投影与一个 routed expert 阶段，保留 dtype、stride、scale 形状、专家 token 分布和当前 stream。比较原阶段与一个相容融合，分别及整体测量量化、copy、GEMM、激活和 combine，检查中间分配与误差，同时覆盖微小 decode 和大 prefill。

比较均匀和真实专家 token 分布，判断融合收益能否在路由不均衡时保留。

## 来源

核对日期：2026-10-14；源码快照见下方链接。

- [MetaX dense INT8 注册与执行](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/registry/linear_kernels/int8.py)。
- [当前 compressed-tensors INT8 MoE](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/registry/quant_config/compressed_tensors_moe/compressed_tensors_moe_w8a8_int8.py)。
- [当前 INT8 MoE oracle](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/model_executor/layers/fused_moe/oracle/int8.py)与[发行兼容说明](https://github.com/MetaX-MACA/vLLM-metax)。

[异构执行](README_zh.md) · [量化](../quantization/README_zh.md) · [知识索引](../README_zh.md)
