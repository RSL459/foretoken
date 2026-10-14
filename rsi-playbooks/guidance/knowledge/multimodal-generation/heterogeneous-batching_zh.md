<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 异构形状与多模态组批兼容性

[English](heterogeneous-batching.md) | 简体中文 | [多模态生成](README_zh.md)

## 请求数不等于计算预算

两个图片请求可能有完全不同的 patch 数；两个视频生成可能有不同 latent 长度、分辨率、guidance 与 adapter。把它们当作两个可互换 sequence slot，会掩盖计算和内存差异。当前引擎已经支持多模态组批；新的研究问题是如何在保留 pipeline 真实约束的前提下减少 padding 与队头等待。

Qwen2.5-VL 的动态空间分辨率体现输入形状差异。当前 vLLM-Omni 扩散执行展示另一类差异：兼容请求可以共享完整 pipeline wave；实现 step contract 的 pipeline 还能在去噪步之间接收新请求。形状、guidance、输出数、LoRA 配置和 pipeline 支持仍然影响兼容性。单个 batch size 不能完整描述这两种执行。

## 一个混合队列怎样形成批次

三个请求依次到达：512²、adapter A；1024²、adapter B；另一个与第一个完全兼容的 512² 请求。FIFO 可能因第二个不兼容而单独执行第一个，尽管第三个可以一起算。向后找兼容请求能形成更有效批次，也可能拖延大请求。因此应比较等待与公平性，不能只看 GPU 吞吐。

对 padding 的编码张量，利用率可示意为 U=sum_i V_i/(n max_i V_i)，V_i 为每项 token 数。256 与 1,024 两行得到 U=0.625。packed 执行可避免这部分填充，但必须保留序列边界、attention mask、位置元数据与输出恢复。某些 attention 成本按 sum_i V_i² 增长，而非 (sum_i V_i)²；packing 不能意外引入跨图片 attention。

扩散又不同：每步更新请求自己的 latent 与 solver 状态。step batching 要逐请求管理 step index、随机状态、conditioning、guidance 和输出归属。若 scheduler 或 VAE 假设统一形状，仅有 packed kernel 还不够。Omni 文档规定了 pipeline 限制，并报告部分 packed 路径没有吞吐收益。

## 条件与现有限制

保留原始输入和模型，只改善组批无需训练。使用已发布模型权重、processor、VAE、文本编码器，并保留逐请求 sampler。降低分辨率或缩短视频改变负载与质量，不属于调度加速。BF16/FP16 kernel 可能要求形状对齐，量化路径、graph capture 可能有不同约束；CUDA 源码支持不等于其他设备可用。

本次核对的 Omni step execution 不支持扩散 cache backend。不同 LoRA 或 scale 会拆开批次。Helios 限单请求；MiniMax H3 的 packing 要求 FlashAttention，且文档说明其组批没有改善已测吞吐。

`max_num_seqs` 限制并发请求数；逐步连续组批还要求 pipeline 实现 step contract。

## 找到正确责任边界的实验

分别改变分辨率、图片数、视频时长、guidance、adapter，保留原始形状和到达时间。匹配最大等待时间比较 FIFO 与兼容性感知组批；再在相同批次成员下比较 padded 与已支持的 packed kernel，分开调度和算子布局。

记录每批 token 或 latent 元素数、padding 比例、各形状排队年龄、实际 batch size、graph replay 与 eager 时间、重编译、峰值内存、TTFT 或首帧尾延迟、完整生成延迟、失败和满足 SLO 的 goodput。加入低频大形状，不能让吞吐策略通过饿死它来显得更快。检查输出归属，以及在 backend 数值容差内的固定 seed 可复现性。

packing 改善 kernel 却不改善服务，应看队列和不兼容的下游阶段；分组提高吞吐但大形状尾延迟爆炸，说明利用率收益来自公平性让步。剩余设计空间是已有 scheduler 边界上的形状感知策略及受支持的 kernel/pipeline 契约。

## 来源与核对状态

核对日期：2026-10-14。

- [Qwen2.5-VL，arXiv:2502.13923v1](https://arxiv.org/html/2502.13923v1)：动态形状与训练样本 packing，作为模型背景。
- [Omni 扩散执行模式](https://docs.vllm.ai/projects/vllm-omni/en/latest/user_guide/diffusion/execution_modes/)与[固定源码](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/user_guide/diffusion/execution_modes.md)：当前兼容性与限制；main `37f094a` 日期为 2026-10-13，release `v0.30.0` 为 2026-09-25。
- [EAServe，arXiv:2609.31551v1](https://arxiv.org/html/2609.31551v1)：近期编码组批时机研究，论文没有证明其实现了专用异构形状 packing。
