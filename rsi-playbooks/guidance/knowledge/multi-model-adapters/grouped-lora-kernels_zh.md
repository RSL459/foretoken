<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 分组 LoRA 算子：不等宽 tile 与低秩并行

[English](grouped-lora-kernels.md) | 简体中文 | [多模型与适配器](README_zh.md)

## 已有多 LoRA 组批之后，还剩什么？

Punica、S-LoRA 奠定了共享基础模型、分组计算低秩更新的路径，当前引擎已经具备这类能力。具体形状的执行效率仍然重要：低 rank 并行度少，打包 QKV 输出宽度不同，未活跃 adapter slot 仍可能占据 launch grid。

SGLang PR #41951 已于 2026-10-13 合并为 `c0584cf`，实现紧凑 expand grid 和可选 split-K shrink。Split-K 默认关闭，设置 `SGLANG_ENABLE_LORA_CSGMV_SPLIT_K=1` 可启用自动形状策略。剩余问题是调度覆盖范围及目标负载的端到端收益。

## 一个适配线性层如何执行

设 X=[m,h]、基础 W=[o,h]，adapter i 的 A_i=[r_i,h]、B_i=[o,r_i]。对应行计算 Y=XW^T+s_i(XA_i^T)B_i^T。基础 GEMM 一起处理所有行；adapter 元数据将行分组，shrink 产生 rank 维中间值，expand 将更新写回对应基础输出。仅使用基础模型的请求没有 adapter 更新。

打包 QKV 时，Q 可能比 K、V 宽。按最大 slice 设矩形 expand grid，会为较小 slice 启动超出范围的 tile。early return 省了运算，却没省 launch 和调度。PR 用 CPU 已知的 slice offset 展平真正有效的 tile，避免从设备拷回元数据。

shrink 则可能在 m、r 很小时闲置大量 SM，却要沿很大的 h 归约。split-K 将归约拆给多个 program，写 FP32 partial，再启动独立归约，最后转换 dtype。并行度增加，但也多了内存流量与一次 launch。合并后的自动可选策略仅针对已测 BF16 rank 32、输入宽度 4,096 或 12,288、特定 tile 参数，不是通用 dispatch 规则。

## 模型、精度与权重

采用兼容的公开基础 checkpoint 与针对其 target module、rank、scale 训练的 PEFT LoRA。kernel 改动不用重训。随机 A/B 张量适合数值探针，不能证明真实质量保持。adapter 可能修改 embedding、attention、MLP 或 MoE expert，形状和分片要求不同。

引用版本的 vLLM shrink 接受 FP16/BF16 输入和匹配权重；batch-invariant 路径使用 FP32 partial。基础模型量化不代表 adapter 也支持量化。TP 改变本地 projection 宽度，应写入形状条件。贡献者报告 H200 验证，其他 NVIDIA GPU、ROCm、MetaX 需要各自可用路径和实测。

split-K 改变求和顺序。合并实现在 deterministic inference 下保留原路径，只归约活跃行与 rank 列，避免读取 graph padding 中未初始化数据。因此应按目标数值标准评估等价性，不能直接假定逐 bit 相同。

## 能解释原因的实验

在合并实现上构造受控对照：矩形 expand 加直接 shrink、只紧凑 expand、只 split-K、两者同时启用。覆盖低 rank、混合 rank、不等宽 QKV、空 slice、小 decode batch、大 prefill batch 与 adapter 热度偏斜。公开 kernel benchmark 可以作为入口；routing 和元数据准备要放入独立完整模型测量。

记录有效及实际启动 tile 数、shrink/expand/reduction 耗时、scratch 字节、SM 利用率、graph replay 和相对 FP32 matmul 的误差。再使用真实 adapter 测量各 adapter TTFT、TPOT、输出长度、错误及 SLO 合格吞吐。slot 重用后检查基础模型与 adapter 请求，暴露残留更新。

只在不等宽 slice 上有收益，说明省掉了空工作；只在小 batch 有收益、prefill 退化，dispatch 应保持形状相关；kernel 改善不进入服务延迟，说明基础 GEMM 或排队占主导。剩余问题是实测 dispatch 和 ragged grid 效率。

## 来源与核对状态

核对日期：2026-10-14。

- [SGLang PR #41951](https://github.com/sgl-project/sglang/pull/41951)：2026-10-13 合并，merge commit 为 `c0584cf9afefdb4a3004a57af8b1aec501d44a4a`，head 为 `a7deef700821501c37fd1de266d4f1f42848d23a`。合并后的 [shrink](https://github.com/sgl-project/sglang/blob/c0584cf9afefdb4a3004a57af8b1aec501d44a4a/python/sglang/kernels/ops/lora/dense/chunked_sgmv_shrink.py) 与 [expand](https://github.com/sgl-project/sglang/blob/c0584cf9afefdb4a3004a57af8b1aec501d44a4a/python/sglang/kernels/ops/lora/dense/chunked_sgmv_expand.py) 定义上述执行路径。
- [SGLang LoRA 文档](https://docs.sglang.io/advanced_features/lora.html)：Triton/CSGMV、组批和 graph 限制；main 版本为 2026-10-13 的 `e9400c5`。[PR #42299](https://github.com/sgl-project/sglang/pull/42299) 已于 2026-10-03 合并，完成 kernel 目录重组。
- [vLLM shrink 源码](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/lora/ops/triton_ops/lora_shrink_op.py)：分组元数据与精度路径，commit `6849ca6` 日期为 2026-10-13。
- [S-LoRA，arXiv:2311.03285v1](https://arxiv.org/html/2311.03285v1)：异构 rank 执行与 paging。
