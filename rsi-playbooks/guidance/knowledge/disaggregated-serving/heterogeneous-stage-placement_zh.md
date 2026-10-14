<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 异构阶段放置

[English](heterogeneous-stage-placement.md) | 简体中文

## 问题与机制

峰值 FLOPs 最高的加速器，不一定最适合推理的每个阶段。Prefill、decode attention、MoE 专家的算力、带宽和容量需求不同。异构放置按阶段选择设备，但不能假定不同阶段可任意共享 kernel 或 KV 表示。

首先建立模型阶段×加速器×dtype×并行方式的可行矩阵。无法装载权重、保存必要状态、执行算子或通过支持的 connector 交换状态的组合，应排除。再测可行组合在阶段延迟预算内的容量，最后优化成本；不支持的组合不是“慢一点”的候选。

可用 `min Σ_s,h n_s,h*c_h` 表示简单目标，同时满足阶段容量、显存、传输和端到端 SLO。n_s,h 为阶段 s 使用硬件 h 的整数 worker 数，c_h 为每 worker 的租用或摊销运营成本，应包括相关主机和网络份额。AFD 中 attention 容量常受 HBM 带宽和 KV 驻留限制，充分批处理后的专家则更能利用算力。P/D 中一个算力强的 P 可服务多个带宽强的 D，但前提是交接成本可接受。

例如一个 P 的容量为 8 请求/s，两个 D 各为 4。把 P 换成便宜但只有 5 请求/s 的设备，即使 D 不变，系统上限也降到 5。把 D 换成显存更小的设备，可能减少驻留并发而违反 TPOT。目标是优化完整路径，不是各算子单独选最低价格。

## 硬件、模型、dtype 与成本

[MegaScale-Infer](https://arxiv.org/html/2504.02263)对 Mixtral-8×22B、DBRX 和 scaled MoE 使用 BF16 权重、activation、KV，选择 H20 做 attention、L40S 做专家，利用带宽／算力单位成本差异。论文归一化采购价格属于历史输入，不是当前云价格。Decode-only 测量在时间上分离了 prefill，端到端收益另行报告。

[FastAFD](https://haoailab.com/blogs/fastafd/)的物理测量是 GB200 NVL72 上的 FP8 MoE。对未来 Rubin 与 LPX/LPU 的数字属于预测，不是经过验证的异构部署。支持 FP8 权重并不证明 KV 传输兼容；跨厂商移动 attention 或 FFN，需要真实 runtime 和数值支持，不能只看 tensor 维度相同。

成本应包含权重副本、转换、主机中转、graph 预热、网络份额和专家小批。低价设备若需要更多 TP rank，会增加同步并占用稀缺拓扑。功率上限也可能改变时钟和最优比例，仅凭设备规格不够。

## 公开实现与当前范围

核对日期为 2026-10-14。AIBrix 的[optimizer](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/python/aibrix/aibrix/gpu_optimizer/optimizer/optimizer.py)把 workload signature 映射到吞吐 bin；[Melange solver](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/python/aibrix/aibrix/gpu_optimizer/optimizer/solver/melange/solver.py)通过整数副本数和 workload slice 分配约束最小化 GPU 成本。

Dynamo 的[planner](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py)已分别决策 P/D 容量。llm-d 的[Kueue 重平衡指南](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/kueue-rebalancing/README.md)提供 quota 准入和借用，不是阶段执行模型或 KV 迁移。

Foretoken 的[E/P/D 示例](../../../../examples/encoder-prefill-decode/README_zh.md)允许按阶段配置资源和 engineArgs。设备执行细节见[异构硬件](../heterogeneous-hardware/README_zh.md)。

## 实验与剩余问题

先 profile 真实阶段／设备矩阵，保持模型输出一致并记录权重／KV dtype。把实测服务曲线与传输成本输入小型整数搜索。在同一预算下比较统一硬件、各阶段独立选便宜设备、联合优化，并对容量误差做敏感性分析，避免噪声决定脆弱方案。

真实服务用相同 trace 比较所选同构与异构部署，记录 SLO goodput、阶段排队、GPU 时间、网络成本和实测功耗。部署后改变长度与命中率，暴露 profile 漂移。保持 checkpoint 和数值验证不变，否则量化变化会伪装成放置收益。后续问题是包含启动／排空成本的在线重分配、稳健尾延迟估计、受支持的跨硬件状态交换。
[返回分离式推理服务](README_zh.md)
